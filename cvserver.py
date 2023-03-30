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

HEADER_LENGTH = 13
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
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._grabed = False
        self.host = host
        self.port = port
        self._clients = {}
        self._is_running = False
        self._queue = queue.Queue()
        self._frame_buffer = None
        

    @property
    def is_running(self):
        return self._is_running

    def isOpened(self, *args, **kwargs):
        if not self.is_running:
            self.start_server()
        while not self._clients:
            time.sleep(1)
        else:
            return True


    def start_server(self):
        self._socket.bind((self.host, self.port))
        self._is_running = True
        threading.Thread(target=self._receiver, daemon=True).start()

    def grab(self, *args, **kwargs):
        if not self._queue.empty():
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
                return None, numpy.empty([0, 0], dtype=numpy.uint8)
            frame = cv2.imdecode(frame_data, cv2.IMREAD_UNCHANGED)
            self._grabed = False
            return client_id, frame
        self._logger.debug("Can't retrieve. Frame don't grabbed")
        return None, numpy.empty([0, 0], dtype=numpy.uint8)

    def read(self, *args, **kwargs):
        self.grab()
        return self.retrieve()
    
    def get(self, *args, **kwargs):
        return None

    def send_order(self, client_id, order):
        if client_id in self._clients.keys() and self._clients[client_id]['status']:
            try:
                data = pickle.dumps(order)
                header = struct.pack("!BI", TY_RESULT, len(data))
                self._socket.sendto(header, self._clients[client_id]['address'])
                self._socket.sendto(data)
            except Exception as e:
                self._logger.error(e)
                client = self._clients[client_id]
                client.update({'status': False})
                self._clients.update(client)

    def _receiver(self):
        self._logger.debug(f"Wait Client To Connect...")
        while self.is_running:
            data, info = self._socket.recvfrom(HEADER_LENGTH)
            header = Pkt(*struct.unpack('!BdI', data))
            if header.type == TY_OPEN:
                self._logger.info(f"Accepted Client From {info[0]}:{info[1]}")
                id = header.id if header.id != 0 else random.random()
                self._clients.update({
                    id: {
                        'address': info,
                        'status': True
                    }
                })
                self._socket.sendto(struct.pack('!BI', TY_OK, 8), info)
                self._socket.sendto(struct.pack('!d', id), info)
            
            elif header.type == TY_CLOSE:
                client = self._clients.get(header.id)
                client.update({'status': False})
                self._clients.update({header.id: client})
                self._logger.info(f"Close Connection From {client['address'][0]}:{client['address'][1]} With {header.id} ID")
            
            elif header.type == TY_FRAME:
                data, _ = self._socket.recvfrom(header.length)
                while header.length > len(data):
                    data += self._socket.recvfrom(header.length - len(data))[0]
                self._logger.debug(f"Received Frame Has {header.length//1024}K Size From {header.id}")
                self._queue.put((header.id, data))
                self._socket.sendto(struct.pack('!BI', TY_FRAME_OK, 0), self._clients[header.id]['address'])
        else:
            self._socket.close()
    
    def release(self):
        self._is_running = False

    def __del__(self):
        self._socket.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    server = CVServer()
    server.start_server()
