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
CHUNK_SIZE = 50000

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
        self._client = {}
        self._is_running = False
        self._queue = queue.Queue()

    @property
    def is_running(self):
        return self._is_running

    @property
    def is_connected(self):
        return len(self._client) > 0


    def start_server(self):
        self._socket.bind((self.host, self.port))
        self._logger.info(f"Start Lisining Into {self.host}:{self.port}")
        self._is_running = True
        threading.Thread(target=self._recv, daemon=True).start()
        threading.Thread(target=self._send, daemon=True).start()

    def stop_server(self):
        if len(self._client):
            self._socket.sendto(struct.pack('!BI', TY_CLOSE, 0), self._client.get('address'))
        self._is_running = False
        self._client_id = {}

    def _recv(self):
        self._logger.debug(f"Wait Client To Connect...")
        while self.is_running:
            data, info = self._socket.recvfrom(HEADER_LENGTH)
            header = Pkt(*struct.unpack('!BdI', data))
            if header.type == TY_OPEN and not len(self._client):
                self._logger.info(f"Accepted Client From {info[0]}:{info[1]}")
                id = header.id if header.id != 0 else random.random()
                self._client['id'] = id
                self._client['address'] = info
                self._socket.sendto(struct.pack('!BI', TY_OK, 8), info)
                self._socket.sendto(struct.pack('!d', id), info)
            
            elif self._client.get('id') == header.id and header.type == TY_CLOSE:
                self._client = {} 
                self._logger.info(f"Close Connection From {info[0]}:{info[1]} With {header.id} ID")
            
            elif self._client.get('id') == header.id and header.type == TY_FRAME_OK:
                self._continue_send = True
        else:
            self._socket.close()



    def send_frame(self, frame):
        if self.is_connected:
            ret, encoded_frame = cv2.imencode(
                ".jpeg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90]
            )
            self._queue.put(encoded_frame.tobytes())


    def _send(self):
        self._continue_send = True
        while self.is_running:
            try:
                if self._continue_send:
                    self._continue_send = False
                    frame = self._queue.get()
                    compressed = zlib.compress(frame)
                    header = struct.pack("!BI", TY_FRAME, len(compressed))
                    chunks = [compressed[i:i+CHUNK_SIZE] for i in range(0, len(compressed), CHUNK_SIZE)]
                    self._socket.sendto(header, self._client.get('address'))
                    for chunk in chunks:
                        self._socket.sendto(chunk, socket.MSG_DONTWAIT, self._client.get('address'))

            except Exception as e:
                self._logger.error(e)
        else:
            self._socket.close()

    def __del__(self):
        if len(self._client):
            self._socket.sendto(struct.pack('!BI', TY_CLOSE, 0), self._client.get('address'))
        self._socket.close()

