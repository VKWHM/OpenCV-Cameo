import logging
import time
import socket
import queue
import zlib
import struct
import numpy
import cv2
import threading


class CVServer(object):
    def __init__(
        self, logger="CVServer"
    ):
        self._logger = logging.getLogger(logger)
        self._logger.debug(f"Initial Class {logger}")
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._client_socket = None
        self._queue = queue.Queue()

    @property
    def connected(self):
        return self._client_socket is not None

    def __del__(self):
        self._socket.close()

    def start_server(self, host="localhost", port=9999):
        self._socket.bind((host, port))
        self._socket.listen(1)
        self._logger.info(f"Start Lisining Into {host}:{port}")
        self.accept_thread = threading.Thread(target=self._accept_client, daemon=True)
        self.accept_thread.start()

    def send_frame(
        self, frame
    ):
        if self.connected:
            ret, encoded_frame = cv2.imencode(".jpeg", frame)
            self._queue.put(encoded_frame.tobytes())

    def _send(self):
        while self.connected:
            frame = self._queue.get()
            compressed = zlib.compress(frame)
            data_length = struct.pack("!I", len(compressed))
            try:
                self._client_socket.send(data_length)
                self._client_socket.send(compressed)
                self._logger.debug(f"Send Frame Has {len(compressed)} Size To Client")
            except:
                self._logger.info(
                    f"{self.address_info[0]}:{self.address_info[1]} Connection Ended"
                )
                self._client_socket = None
        else:
            self.accept_thread = threading.Thread(
                target=self._accept_client, daemon=True
            )
            self.accept_thread.start()

    def _accept_client(self):
        self._logger.debug(f"Wait Client To Connect...")
        self._client_socket, self.address_info = self._socket.accept()
        self._logger.info(
            f"Accepted Client From {self.address_info[0]}:{self.address_info[1]}"
        )
        self.send_thread = threading.Thread(target=self._send, daemon=True)
        self.send_thread.start()
        return

