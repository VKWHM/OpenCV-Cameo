import cv2
import logging
import argparse

try:
    import colorlog
except ImportError:
    import sys

    sys.stderr.write("colorlog Module Is Not Installed !!\n")
    sys.exit(1)


import filters
from manager import CaptureManager, WindowManager
from tracker import FaceTracker
from cvserver import CVServer
from cvclient import CVClient


class Cameo(object):
    def __init__(self, Capture, logger="Cameo"):
        self._logger = logging.getLogger(logger)
        self._windowManager = WindowManager("Window", self.onKeypress)
        self._captureManager = CaptureManager(
            Capture,
            self._windowManager,
        )

        self._faceTrack = FaceTracker(scaleFactor=1.09, minNeighbors=10)
        self.shouldTrackingFace = False

        self._curveFilter = filters.SharpenFilter()
        self.applyFilter = False

    def run(self):
        """
        Run Main loop.
        """
        self._windowManager.createWindow()
        while self._windowManager.isWindowCreated:
            with self._captureManager as frame:
                if frame is not None:
                    if self.shouldTrackingFace:
                        self._faceTrack.update(frame)
                        self._faceTrack.drawDebugRects(frame)

                if self.applyFilter:
                    self._curveFilter.apply(frame, frame)
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
        elif keycode == ord("a"):
            self._logger.info(
                "Filter Applying "
                + ("Started" if not self.applyFilter else "Stoped")
            )
            self.applyFilter = not self.applyFilter
        elif keycode == ord("x"):
            self._logger.info(
                "Face Tracking "
                + ("Started" if not self.shouldTrackingFace else "Stoped")
            )
            self.shouldTrackingFace = not self.shouldTrackingFace
        elif keycode == 27:  # ESC
            self._windowManager.destroyWindow()


class CameoServer(Cameo):
    def __init__(self, Capture, address='localhost', logger="CameoServer"):
        self.address = address
        self._logger = logging.getLogger(logger)
        self._server = CVServer()
        self._captureManager = CaptureManager(
            Capture
        )

    def run(self):
        """
        Run Main loop.
        """
        self._server.start_server(self.address)
        while True:
            with self._captureManager as frame:
                if frame is not None:
                    self._server.send_frame(frame)

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
        self._logger.debug(f"Initial Class {loggerName}")

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
        "-c",
        "--client-mode",
        dest='client',
        action="store_true",
        help="Enable Client Mode And Accept Frames From CameoServer Has Address Given On 'cap' Parameter",
    )
    parser.add_argument(
        "-s",
        "--server",
        dest='address',
        help="Enable Server Mode To Start Lisining On The Address Given",
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
    return parser


if __name__ == "__main__":
    parser = get_args()
    cap, client, address, log, depth = vars(parser.parse_args()).values()
    colorlog.basicConfig(
        format="[%(asctime)s.%(msecs)03d] [%(log_color)s%(levelname)s%(reset)s] (%(name)s): %(log_color)s%(message)s%(reset)s",
        level=getattr(logging, log.upper()),
        datefmt="%H:%M:%S",
    )
    
    if len(cap) < 3:
        cap = int(cap)
    if client and address:
        parser.error("Can't Enable Server Mode And Client Mode Same Time")
    elif client:
        Cameo(CVClient(cap)).run()
    elif address:
        CameoServer(cv2.VideoCapture(cap), address).run()
    elif depth:
        CameoDepth(cap).run()
    else:
        Cameo(cv2.VideoCapture(cap)).run()

