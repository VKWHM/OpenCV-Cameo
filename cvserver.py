import logging
import pickle
import time
import select
import socket
import queue
import zlib
import struct
import numpy
import cv2
import threading


class CVServer(object):
    DATA_LENGTH = 4
    TYPE_LENGTH = 1
    TY_RECEIVER = 0
    TY_SENDER = 1
    TY_OK = 2

    def __init__(self, logger="CVServer"):
        self._logger = logging.getLogger(logger)
        self._logger.debug(f"Initial Class {logger}")
        self._is_running = False
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._receiver_connected = False
        self._sender_connected = False
        self._queue = queue.Queue()

    @property
    def is_server_running(self):
        return self._is_running

    @property
    def is_sender_connected(self):
        return self._sender_connected

    @property
    def is_receiver_connected(self):
        return self._receiver_connected

    def stop_server(self):
        self._receiver_connected = False
        self._sender_connected = False
        self._is_running = False
        self.accept_thread.join()
        self.recv_thread.join()
        self.send_thread.join()

    def __del__(self):
        self._socket.close()

    def start_server(self, host="localhost", port=9999):
        self._socket.bind((host, port))
        self._socket.listen(1)
        self._logger.info(f"Start Lisining Into {host}:{port}")
        self._is_running = True
        self.accept_thread = threading.Thread(target=self._accept_client, daemon=True)
        self.accept_thread.start()

    def send_frame(self, frame):
        if self.is_receiver_connected:
            if self._queue.empty():
                ret, encoded_frame = cv2.imencode(
                    ".jpeg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90]
                )
                self._queue.put(encoded_frame.tobytes())

    def _recv(self, socket):
        socket, address = socket
        while self.is_sender_connected:
            header = socket.recv(CVServer.DATA_LENGTH)
            if not header:
                self._sender_connected = False
                break
            data_length = struct.unpack("!I", header)[0]
            data = socket.recv(data_length)
            while data_length > len(data):
                data += socket.recv(data_length - len(data))
            orders = pickle.loads(data)
            print(orders)
        else:
            socket.close()

    def _send(self, socket):
        socket, address = socket
        while self.is_receiver_connected:
            try:
                frame = self._queue.get()
                compressed = zlib.compress(frame)
                data_length = struct.pack("!I", len(compressed))
                socket.send(data_length)
                socket.send(compressed)
                self._logger.debug(
                    f"Send Frame Has {len(compressed)//1024}K Size To Client"
                )
                self._logger.debug(f"Wait Recv")
                socket.recv(CVServer.TYPE_LENGTH)

            except Exception as e:
                self._logger.error(e)
                self._logger.info(f"{address[0]}:{address[1]} Connection Ended")
                del self._queue
                self._queue = queue.Queue()
                self._receiver_connected = False
        else:
            socket.close()

    def _accept_client(self):
        while self._is_running:
            self._logger.debug(f"Wait Client To Connect...")
            client, info = self._socket.accept()
            self._logger.info(f"Accepted Client From {info[0]}:{info[1]}")
            type_data = client.recv(CVServer.TYPE_LENGTH)
            client_type = struct.unpack("!b", type_data)[0]

            if client_type == CVServer.TY_RECEIVER:
                self._logger.debug("Client Is Receiver Type")
                if not self._receiver_connected:
                    self._receiver_connected = True
                    socket = (client, info)
                    self.send_thread = threading.Thread(
                        target=self._send, args=(socket,), daemon=True
                    )
                    self.send_thread.start()
                else:
                    self._logger.warning(
                        "Receiver Type Client Aleardy Accepted, Deny..."
                    )
                    client.close()
            elif client_type == CVServer.TY_SENDER:
                self._logger.debug("Client Is Sender Type")
                if not self._sender_connected:
                    self._sender_connected = True
                    socket = (client, info)
                    self.recv_thread = threading.Thread(
                        target=self._recv, args=(socket,), daemon=True
                    )
                    self.recv_thread.start()
                else:
                    self._logger.warning("Sender Type Client Aleardy Accepted, Deny...")
                    client.close()
            else:
                self._logger.error(f"Unknown Client")
                client.close()
        else:
            self._socket.close()

