import logging
import pickle
import socket
import zlib
import struct
import numpy
import cv2


class CVClient:
    DATA_LENGTH = 4
    TYPE_LENGTH = 1
    TY_RECEIVER = 0
    TY_SENDER = 1
    TY_OK = 2

    def __init__(
        self, host="localhost", port=9999, enable_sender=False, logger="CVClient"
    ):
        self._logger = logging.getLogger(logger)
        self._logger.debug(f"Initial Class {logger}")
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._frame_buffer = None
        self._grabed = False

        try:
            self._socket.connect((host, port))
            self._socket.send(struct.pack("!b", CVClient.TY_RECEIVER))
            self._isOpened = True
            self._logger.info(f"Connected To {host}:{port}")
        except ConnectionRefusedError:
            self._logger.error(f"Can't Connect to {host}:{port}")
            self._isOpened = False
        except Exception as e:
            self._logger.error(e)
            self._isOpened = False

        if enable_sender:
            try:
                self._send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._send_socket.connect((host, port))
                self._send_socket.send(struct.pack("!b", CVClient.TY_SENDER))
                self._canSend = True
                self._logger.info(f"Sender Connected To {host}:{port}")
            except ConnectionRefusedError:
                self._logger.error(f"Can't Connect to {host}:{port}")
                self._canSend = False
            except Exception as e:
                self._logger.error(e)
                self._canSend = False
        else:
            self._canSend = False

    def __del__(self):
        self._socket.close()

    def isOpened(self):
        return self._isOpened

    def grab(self, *args, **kwargs):
        if self._isOpened:
            header = self._socket.recv(CVClient.DATA_LENGTH)
            if not header:
                self._logger.error("Connection Ended")
                self._isOpened = False
                return False
            self._frame_size = struct.unpack("!I", header)[0]
            self._frame_buffer = self._socket.recv(self._frame_size)
            while self._frame_size - len(self._frame_buffer) > 0:
                self._frame_buffer += self._socket.recv(self._frame_size)
            self._socket.send(struct.pack("!b", CVClient.TY_OK))
            self._grabed = True
            self._logger.debug(f"Received Frame Has {self._frame_size//1024}K Size")
        return self._grabed

    def retrieve(self, *args, **kwargs):
        if self._grabed:
            frame_data = numpy.frombuffer(
                zlib.decompress(self._frame_buffer),
                dtype=numpy.uint8,
            )
            self._logger.debug(f"Decode Frame")
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

    def send_order(self, order):
        if self._canSend:
            try:
                data = pickle.dumps(order)
                data_length = struct.pack("!I", len(data))
                self._send_socket.send(data_length)
                self._send_socket.send(data)
            except Exception as e:
                self._logger.error(e)
                self._canSend = False

    def release(self):
        if self._isOpened:
            self._socket.close()
            self._isOpened = False

