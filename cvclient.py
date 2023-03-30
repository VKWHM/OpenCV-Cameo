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

HEADER_LENGTH = 5
TYPE_LENGTH = 1
CHUNK_SIZE = 60000

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
        self._orders = queue.Queue()
        self._id = None

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
                threading.Thread(target=self._send, daemon=True).start()
                threading.Thread(target=self._recv, daemon=True).start()
                return True
        except socket.timeout:
            self._logger.critical(f"Timeout! Can't Connect To Server")
            return False
        except Exception as e:
            self._logger.error(e)
            return False

    
    def get_orders(self):
        if not self._orders.empty():
            return self._orders.get()
        return None
    
    @property
    def is_connected(self):
        return self._connection_established

    def send_frame(self, frame):
        if self.is_connected:
            if self._queue.empty():
                ret, encoded_frame = cv2.imencode(
                    ".jpeg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90]
                )
                self._queue.put(encoded_frame.tobytes())

    def _recv(self):
        while self.is_connected:
            try:
                data, _ = self._socket.recvfrom(HEADER_LENGTH)
                header = Pkt(*struct.unpack('!BI', data))
                if header.type == TY_FRAME_OK:
                    self._continue_send = True
                elif header.type == TY_RESULT:
                    data, _ = self._socket.recvfrom(header.length)
                    orders = pickle.loads(data)
                    self._orders.put(orders)
            except socket.timeout:
                self._connection_established = False

    def _send(self):
        self._continue_send = True
        while self.is_connected:
            try:
                if self._continue_send:
                    self._continue_send = False
                    frame = self._queue.get()
                    compressed = zlib.compress(frame)
                    header = struct.pack("!BdI", TY_FRAME, self._id, len(compressed))
                    chunks = [compressed[i:i+CHUNK_SIZE] for i in range(0, len(compressed), CHUNK_SIZE)]
                    self._socket.sendto(header, self.server_address)
                    for chunk in chunks:
                        self._socket.sendto(chunk, socket.MSG_DONTWAIT, self.server_address)

            except KeyboardInterrupt as e:
                self._logger.error(e)

    def __del__(self):
        if self._connection_established:
            self._socket.sendto(struct.pack('!BdI', TY_CLOSE, self._id, 0), self.server_address)
        self._socket.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    client = CVClient()
