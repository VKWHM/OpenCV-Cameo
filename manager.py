import cv2
from urllib.request import urlopen
import numpy
import time
import logging


class CaptureManager(object):
    def __init__(
        self,
        capture,
        previewWindowManager=None,
        shouldMirrorPreview=False,
        shouldConvertBit10To8=False,
        loggerName="CaptureManager",
    ):
        self._logger = logging.getLogger(loggerName)
        self._logger.debug(f"Initial Class {loggerName}")
        self.previewWindowManager = previewWindowManager
        self.shouldMirrorPreview = shouldMirrorPreview
        self.shouldConvertBit10To8 = shouldConvertBit10To8
        self._capture = capture
        self._channel = 0
        self._enteredFrame = False
        self._frame = None
        self._videoFilename = None
        self._imageFilename = None
        self._videoEncoding = None
        self._frameElpased = 0
        self._fpsEstimate = None
        self._startTime = None
        self._videoWriter = None
        if shouldMirrorPreview:
            self._logger.debug(f"Mirror Frame Enabled")

    def __enter__(self):
        self.enterFrame()
        return self.frame

    def __exit__(self, exc_type, exc_value, traceback):
        self.exitFrame()

    @property
    def fps(self):
        return "{:.2f} FPS".format(self._fpsEstimate) if self._fpsEstimate is not None else "0.0 FPS"

    @property
    def channel(self):
        return self._channel

    @channel.setter
    def channel(self, value):
        if self._channel != value:
            self._channel = value
            self._frame = None

    @property
    def frame(self):
        if self._enteredFrame and self._frame is None:
            self._logger.debug(f"Retrieve Frame From Channel {self._channel}")
            _, self._frame = self._capture.retrieve(self._frame, self._channel)
            if self.shouldConvertBit10To8 and self._frame is not None:
                if self._frame.dtype == numpy.uint16:
                    self._logger.debug(f"Convert Frame Bit From 10 To 8")
                    self._frame = (self._frame >> 2).astype(numpy.uint8)
                else:
                    self._logger.warning(f"Can't Convert Bit, Frame Already 8 Bit.")
        return self._frame

    @property
    def isWritingImage(self):
        return self._imageFilename is not None

    @property
    def isWritingVideo(self):
        return self._videoFilename is not None

    def enterFrame(self):
        """
        Capture the next frame, if any.
        """
        if self._capture is not None:
            if not self._capture.isOpened():
                self._logger.error("The Device Not Opened, Die...")
                raise cv2.error(
                    "The device not opened. Make sure the device is working"
                )
            self._logger.debug(f"Grabing Frame From")
            self._enteredFrame = self._capture.grab()

    def exitFrame(self):
        """
        Draw to the window. Write to files. Release the frame.
        """
        if self._frame is None:
            self._enteredFrame = False
            return
        if self._frameElpased == 0:
            self._startTime = time.time()
        else:
            timeElpased = time.time()
            self._fpsEstimate = self._frameElpased / (timeElpased - self._startTime)
        self._frameElpased += 1

        if self.previewWindowManager is not None:
            if self.shouldMirrorPreview:
                mirroredFrame = numpy.fliplr(self._frame)
                self.previewWindowManager.show(mirroredFrame)
            else:
                self.previewWindowManager.show(self._frame)

        if self.isWritingImage:
            self._logger.info(f"Screenshot Is Being Saved Into {self._imageFilename}")
            cv2.imwrite(self._imageFilename, self._frame)
            self._imageFilename = None

        self._writeVideoFrame()
        self._frame = None
        self._enteredFrame = False

    def writeImage(self, filename):
        """
        Write the next exited frame to an image file.
        """
        self._logger.debug(f"Set Image File Name {filename}")
        self._imageFilename = filename

    def startWriteVideo(self, filename, encoding=cv2.VideoWriter_fourcc(*"MJPG")):
        """
        Start writing exited frames to a video file.
        """
        self._logger.info(f"Start Video Recording Into {filename}")
        self._videoFilename = filename
        self._videoEncoding = encoding

    def stopWriteVideo(self):
        """
        Stop writing exited frames to a video file.
        """
        self._logger.info(f"Stop Writing Video")
        self._videoEncoding = None
        self._videoFilename = None
        self._videoWriter = None

    def _writeVideoFrame(self):
        if not self.isWritingVideo:
            return
        if self._videoWriter is None:
            self._logger.debug(f"Video Writer is none. Initial It...")
            fps = self._capture.get(cv2.CAP_PROP_FPS)
            self._logger.debug(f"Get FPS from Camera {fps}")
            if fps is None or (fps is not None and fps <= 0.0):
                if self._frameElpased < 20:
                    return
                else:
                    fps = int(self._fpsEstimate)
                    self._logger.debug(f"Set Estimated FPS {fps}")
            try:
                size = (
                    int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                )
            except TypeError:
                size = self._frame.shape[:2][::-1]
            self._videoWriter = cv2.VideoWriter(
                self._videoFilename, self._videoEncoding, fps, size
            )
        self._logger.debug(f"Write Frame {self._frameElpased}")
        self._videoWriter.write(self._frame)



class WindowManager(object):
    def __init__(
        self,
        windowName,
        keypressCallback=None,
        windowSize=None,
        loggerName="WindowManager",
    ):
        self._logger = logging.getLogger(loggerName)
        self._logger.debug(f"Initial Class {loggerName}")
        self.keypressCallback = keypressCallback
        self.full_screen = False
        self._windowName = windowName
        self._isWindowCreated = False
        self._windowSize = windowSize

    @property
    def isWindowCreated(self):
        return self._isWindowCreated

    def createWindow(self):
        self._logger.info(f"Create Window as {self._windowName}")
        cv2.namedWindow(self._windowName)
        if self._windowSize is not None:
            self._logger.debug(f"Resize window to {self._windowSize}")
            cv2.resizeWindow(self._windowName, *self._windowSize)
        self._isWindowCreated = True

    def show(self, frame):
        self._logger.debug(f"Show Frame")
        cv2.imshow(self._windowName, frame)

    def destroyWindow(self):
        self._logger.info(f"Destroy Window {self._windowName}")
        cv2.destroyWindow(self._windowName)
        self._isWindowCreated = False

    def processEvent(self):
        keycode = cv2.waitKey(1)
        if self.keypressCallback is not None and keycode != -1:
            self._logger.debug(f"Process Pressed Key {keycode}")
            self.keypressCallback(self._windowName, keycode)

