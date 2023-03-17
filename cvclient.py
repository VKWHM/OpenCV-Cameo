import logging
import socket
import zlib
import struct
import numpy
import cv2


class CVClient:
    def __init__(self, host="localhost", port=9999, logger="CVClient"):
        self._logger = logging.getLogger(logger)
        self._logger.debug(f"Initial Class {logger}")
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._frame_buffer = bytearray(1024 * 1024 * 10)
        self._grabed = False
        try:
            self._socket.connect((host, port))
            self._isOpened = True
            self._logger.info(f"Connected To {host}:{port}")
        except ConnectionRefusedError:
            self._logger.error(f"Can't Connect to {host}:{port}")
            self._isOpened = False

    def __del__(self):
        self._socket.close()

    def isOpened(self):
        return self._isOpened

    def grab(self, *args, **kwargs):
        if self._isOpened:
            header = self._socket.recv(4)
            if not header:
                self._logger.error("Connection Ended")
                self._isOpened = False
                return False
            self._frame_size = struct.unpack("!I", header)[0]
            self._socket.recv_into(self._frame_buffer, self._frame_size)
            self._grabed = True
            self._logger.debug(f"Received Frame Has {self._frame_size} Size")
        return self._grabed

    def retrieve(self, *args, **kwargs):
        if self._grabed:
            frame_data = numpy.frombuffer(
                zlib.decompress(self._frame_buffer[: self._frame_size]),
                dtype=numpy.uint8,
            )
            frame = cv2.imdecode(frame_data, cv2.IMREAD_UNCHANGED)
            self._grabed = False
            return True, frame
        self._logger.debug("Can't retrieve. Frame don't grabbed")
        return False, numpy.empty([0, 0], dtype=numpy.uint8)

    def read(self, *args, **kwargs):
        self.grab()
        return self.retrieve()

    def get(self, *args, **kwargs):
        return None

    def release(self):
        if self._isOpened:
            self._socket.close()
            self._isOpened = False

