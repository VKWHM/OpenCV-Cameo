import cv2
import logging
import filters
import argparse

try:
    import colorlog
except ImportError:
    import sys

    sys.stderr.write("colorlog Module Is Not Installed !!\n")
    sys.exit(1)

from manager import CaptureManager, WindowManager
from tracker import FaceTracker


class Cameo(object):
    def __init__(self, Capture, logger="Cameo"):
        self._logger = logging.getLogger(logger)
        self._windowManager = WindowManager("Window", self.onKeypress)
        self._captureManager = CaptureManager(
            cv2.VideoCapture(Capture), self._windowManager, False
        )
        self._curveFilter = filters.SharpenFilter()
        self._faceTrack = FaceTracker(scaleFactor=1.09, minNeighbors=10)
        self._shouldTrackingFace = False

    def run(self):
        """
        Run Main loop.
        """
        self._windowManager.createWindow()
        while self._windowManager.isWindowCreated:
            with self._captureManager as frame:
                if frame is not None:
                    if self._shouldTrackingFace:
                        self._faceTrack.update(frame)
                        self._faceTrack.drawDebugRects(frame)
                    # filters.strokeEdges(frame, frame, edgeKsize=5)
                    # self._curveFilter.apply(frame, frame)
                    pass
            self._windowManager.processEvent()

    def onKeypress(self, keycode):
        """
        Handle a keypress.
        space -> Take a screenshot
        x -> Start/Stop Face Tracking
        tab -> Start/Stop recording a screencast.
        escape -> Quit.
        """
        if keycode == 32:  # space
            self._captureManager.writeImage("screenshot.png")
        elif keycode == 9:  # TAB
            if not self._captureManager.isWritingVideo:
                self._captureManager.startWriteVideo(
                    "screencast.mp4", cv2.VideoWriter_fourcc(*"mp4v")
                )
            else:
                self._captureManager.stopWriteVideo()
        elif keycode == ord("x"):
            self._logger.info(
                "Face Tracking "
                + ("Started" if not self._shouldTrackingFace else "Stoped")
            )
            self._shouldTrackingFace = not self._shouldTrackingFace
        elif keycode == 27:  # ESC
            self._windowManager.destroyWindow()


class CameoDepth(Cameo):
    def __init__(self, loggerName="CameoDepth"):
        self._windowManager = WindowManager("Cameo", self.onKeypress)
        # device = cv2.CAP_OPENNI2_ASUS
        device = cv2.CAP_OPENNI2
        self._captureManager = CaptureManager(
            cv2.VideoCapture(device), self._windowManager, True, True
        )
        self._curveFilter = filters.SharpenFilter()
        self._logger = logging.getLogger(loggerName)
        self._logger.debug(f"Initial Class {loggerName=}")

    def run(self):
        """
        Run the main loop
        """
        self._windowManager.createWindow()
        while self._windowManager.isWindowCreated:
            self._captureManager.enterFrame()
            self._captureManager.channel = cv2.CAP_OPENNI_DISPARITY_MAP
            disparityMap = self._captureManager.frame
            self._captureManager.channel = cv2.CAP_OPENNI_VALID_DEPTH_MASK
            validDepthMask = self._captureManager.frame
            self._captureManager.channel = cv2.CAP_OPENNI_BGR_IMAGE
            frame = self._captureManager.frame
            if frame is None:
                self._logger.debug(
                    "BGR frame faild, try to capture an infrared frame instead"
                )
                self._captureManager.channel = cv2.CAP_OPENNI_IR_IMAGE
                frame = self._captureManager.frame
            if frame is not None:
                mask = depth.createMedianMask(disparityMap, validDepthMask)
                frame[mask == 0] = 0
                if self._captureManager.channel == cv2.CAP_OPENNI_BGR_IMAGE:
                    self._curveFilter.apply(frame, frame)
            self._captureManager.exitFrame()
            self._windowManager.processEvent()
            return


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "cap",
        default=0,
        help="video file or a capturing device or an IP video stream for video capturing.",
    )
    parser.add_argument(
        "-l",
        "--log-level",
        dest="log",
        default="warning",
        choices=["critical", "error", "warning", "info", "debug"],
        help="Level for logging",
    )
    parser.add_argument(
        "-d", "--use-depth", dest="depth", action="store_true", help="Use Depth Camera"
    )
    return vars(parser.parse_args())


if __name__ == "__main__":
    cap, log, depth = get_args().values()
    if len(cap) < 3:
        cap = int(cap)
    colorlog.basicConfig(
        format="[%(asctime)s.%(msecs)03d] [%(log_color)s%(levelname)s%(reset)s] (%(name)s): %(log_color)s%(message)s%(reset)s",
        level=getattr(logging, log.upper()),
        datefmt="%H:%M:%S",
    )
    if depth:
        CameoDepth(cap).run()
    else:
        Cameo(cap).run()

