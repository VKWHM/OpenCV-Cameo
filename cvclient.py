import logging
import pickle
import socket
import zlib
import struct
import numpy
import cv2
import ctypes
import queue
import threading

HEADER_LENGTH = struct.calcsize('!BI')
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
        ('length', ctypes.c_uint)
    ]

class CVClient:

    def __init__(
        self, host="localhost", port=9999, logger="CVClient"
    ):
        self._logger = logging.getLogger(logger)
        self._logger.debug(f"Initial Class {logger}")
        self.server_address = (host, port)
        self._queue = queue.Queue()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.settimeout(5)
        self._connection_established = False
        self._id = None
        self.connect()

    def disconnect(self):
        if self._connection_established:
            self._logger.info("Disconnected With Server")
            self._connection_established = False
            self._socket.sendto(struct.pack('!BdI', TY_CLOSE, self._id, 0), self.server_address)

    def connect(self):
        try:
            self._socket.sendto(struct.pack("!BdI", TY_OPEN, self._id if self._id is not None else 0, 0), self.server_address)
            data, _ = self._socket.recvfrom(HEADER_LENGTH)
            header = Pkt(*struct.unpack('!BI', data))
            if header.type == TY_OK:
                self._id = struct.unpack('!d', self._socket.recvfrom(header.length)[0])[0]
                self._logger.info(f"Connected To {self.server_address[0]}:{self.server_address[1]} With {self._id} ID")
                self._connection_established = True
                threading.Thread(target=self._recv, daemon=True).start()
                return True

        except socket.timeout:
            self._logger.critical(f"Timeout! Can't Connect To Server")
            return False
        except Exception as e:
            self._logger.error(e)
            return False

    @property
    def is_connected(self):
        return self._connection_established

    def _recv(self):
        while self.is_connected:
            try:
                data, info = self._socket.recvfrom(HEADER_LENGTH)
                header = Pkt(*struct.unpack('!BI', data))
                if header.type == TY_CLOSE:
                    self._logger.info(f"Close Connection")
                    self._connection_established = False
                
                elif header.type == TY_FRAME:
                    data, _ = self._socket.recvfrom(header.length)
                    while header.length > len(data):
                        data += self._socket.recvfrom(header.length - len(data))[0]
                    self._logger.debug(f"Received Frame Has {header.length//1024}K Size ")
                    self._queue.put(data)
                    self._socket.sendto(struct.pack('!BdI', TY_FRAME_OK, self._id, 0), self.server_address)
            except socket.timeout:
                self._connection_established = False
        else:
            self._socket.close()

    def __del__(self):
        if self._connection_established:
            self._socket.sendto(struct.pack('!BdI', TY_CLOSE, 0), self._id, self.server_address)
        self._socket.close()

    def isOpened(self):
        return self.is_connected

    def grab(self, *args, **kwargs):
        if self.is_connected:
            self._frame_buffer = self._queue.get()
            self._grabed = True
        return self._grabed

    def retrieve(self, *args, **kwargs):
        if self._grabed:
            try:
                frame_data = numpy.frombuffer(
                    zlib.decompress(self._frame_buffer),
                    dtype=numpy.uint8,
                )
            except zlib.error:
                self._logger.debug("Can't retrieve Frame. Decompress Error")
                return None, numpy.empty([0, 0], dtype=numpy.uint8)
            frame = cv2.imdecode(frame_data, cv2.IMREAD_UNCHANGED)
            self._grabed = False
            return True, frame
        
        return None, numpy.empty([0, 0], dtype=numpy.uint8)

    def read(self, *args, **kwargs):
        self.grab()
        return self.retrieve()
    
    def get(self, *args, **kwargs):
        return None

    def release(self):
        if self.is_connected:
            self._socket.sendto(struct.pack('!BdI', TY_CLOSE, self._id, 0), self.server_address)
            self._socket.close()
            self._connection_established = False

