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
import random
import ctypes

HEADER_LENGTH = struct.calcsize('!BdI')
TYPE_LENGTH = 1

TY_OPEN = 3
TY_CLOSE = 6
TY_RESULT = 1
TY_OK = 2
TY_FRAME = 4
TY_FRAME_OK = 5

class Pkt(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_uint8),
        ('id', ctypes.c_double),
        ('length', ctypes.c_uint)
    ]

class CVServer(object):

    def __init__(self, host="0.0.0.0", port=9999, logger="CVServer"):
        self._logger = logging.getLogger(logger)
        self._logger.debug(f"Initial Class {logger}")
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self._grabed = False
        self.host = host
        self.port = port
        self._clients = {}
        self._is_running = False
        self._queue = queue.Queue()
        self._frame_buffer = None
        

    @property
    def clients(self):
        for key, value in self._clients.items():
            if value.get('status') is True:
                yield key
    
    @property
    def is_running(self):
        return self._is_running

    def stop_server(self):
        self._is_running = False
        self._clients = {}
        self._queue = queue.Queue()
        return self.is_running

    def start_server(self):
        self._socket.bind((self.host, self.port))
        self._socket.listen(1)
        self._is_running = True
        self._logger.info("Start Server To Lisening Incoming Connection")
        threading.Thread(target=self._accept_client, daemon=True).start()

    def send_order(self, client_id, order):
        if client_id in self._clients.keys() and self._clients[client_id]['status']:
            try:
                socket = self._clients[client_id]['socket']
                self._logger.info(f"Send {order} Orders To {client_id}")
                data = pickle.dumps(order)
                header = struct.pack("!BI", TY_RESULT, len(data))
                socket.send(header + data)
            except Exception as e:
                self._logger.error(e)
                client = self._clients[id]
                client.update({'status': False})
                self._clients[id].update(client)
                self._logger.info(f"Close Connection From {client['address'][0]}:{client['address'][1]} With {id} ID")
                socket.close()

    def _receiver(self, id):
        client_socket = self._clients[id]['socket']
        while self.is_running and self._clients[id]['status']:
            try:
                header = Pkt(*struct.unpack('!BdI', client_socket.recv(HEADER_LENGTH)))
                if header.id != id:
                    self._logger.warning(f"Invalid ID. From {id} Received {header.id} ID")
                    raise

                elif header.type == TY_CLOSE:
                    raise

                elif header.type == TY_FRAME:
                    data = client_socket.recv(header.length)
                    while header.length > len(data):
                        data += client_socket.recv(header.length - len(data))
                    self._logger.debug(f"Received Frame Has {header.length//1024}K Size From {header.id}")
                    self._queue.put((header.id, data))
                    client_socket.send(struct.pack('!BI', TY_FRAME_OK, 0))

            except Exception:
                client = self._clients[id]
                client.update({'status': False})
                self._clients[id].update(client)
        else:
            self._logger.info(f"Close Connection From {client['address'][0]}:{client['address'][1]} With {id} ID")
            client_socket.close()
    
    def _accept_client(self):
        while self._is_running:
            self._logger.debug(f"Wait Client To Connect...")
            client, info = self._socket.accept()
            try:
                header = Pkt(*struct.unpack('!BdI', client.recv(HEADER_LENGTH)))
                if header.type == TY_OPEN:
                    self._logger.info(f"Accepted Client From {info[0]}:{info[1]}")
                    id = header.id if header.id != 0 else random.random()
                    self._clients.update({
                        id: {
                            'socket': client,
                            'address': info,
                            'status': True
                        }
                    })
                    threading.Thread(target=self._receiver, args=(id,), daemon=True).start()
                    client.send(struct.pack('!BI', TY_OK, 8) + struct.pack('!d', id))
                else:
                    self._logger.debug(f"Deny Connection From {info[0]}:{info[1]}")
                    client.close()
            except Exception as e:
                self._logger.warning(e)
                client.close()
        else:
            self._socket.close()

    def isOpened(self, *args, **kwargs):
        if not self.is_running:
            self.start_server()
        while not self._clients:
            time.sleep(1)
        else:
            for key, value in self._clients.items():
                if value.get('status') == True:
                    return True
        return False


    def grab(self, *args, **kwargs):
        if len(list(self.clients)):
            self._frame_buffer = self._queue.get()
            self._grabed = True
        return self._grabed

    def retrieve(self, *args, **kwargs):
        if self._grabed:
            client_id, frame_buffer = self._frame_buffer
            try:
                frame_data = numpy.frombuffer(
                    zlib.decompress(frame_buffer),
                    dtype=numpy.uint8,
                )
            except zlib.error:
                self._logger.debug("Can't retrieve Frame. Decompress Error")
                return None, numpy.empty([0, 0], dtype=numpy.uint8)
            frame = cv2.imdecode(frame_data, cv2.IMREAD_UNCHANGED)
            self._grabed = False
            return client_id, frame
        
        return None, numpy.empty([0, 0], dtype=numpy.uint8)

    def read(self, *args, **kwargs):
        if not self.grab():
            while not len(list(self.clients)):
                time.sleep(0.5)
            else:
                self.grab()
        return self.retrieve()
    
    def get(self, *args, **kwargs):
        return None

    def release(self):
        self._is_running = False

    def __del__(self):
        self._socket.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    server = CVServer()
    server.start_server()
    while True:
        time.sleep(1)
