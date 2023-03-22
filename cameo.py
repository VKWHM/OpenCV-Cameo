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
from tracker import FaceTracker, ObjectTracker
from cvserver import CVServer
from cvclient import CVClient


class Cameo(object):
    def __init__(self, Capture, logger="Cameo", detect=None, trashold=None):
        self._logger = logging.getLogger(logger)
        self._windowManager = WindowManager("Window", self.onKeypress)
        self._captureManager = CaptureManager(
            Capture,
            self._windowManager,
        )

        self._track = None
        self.shouldTracking = False
        if detect:
            self._track = ObjectTracker(detect, scaleFactor=trashold)

        self._faceTrack = FaceTracker(scaleFactor=trashold, minNeighbors=10)
        self.shouldTrackingFace = False

        self._curveFilter = None
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

                    if self._track is not None and self.shouldTracking:
                        self._track.update(frame)
                        self._track.drawDebugRects(frame)

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
        elif keycode in [ord('b'), ord('s'), ord('e'), ord('f')]:
            if keycode == ord("b"):
                self._logger.info(
                    "Blur Filter Applying "
                    + ("Started" if not self.applyFilter else "Stoped")
                )
                self._curveFilter = filters.BlurFilter()
            elif keycode == ord("s"):
                self._logger.info(
                    "Sharpen Filter Applying "
                    + ("Started" if not self.applyFilter else "Stoped")
                )
                self._curveFilter = filters.SharpenFilter()
            elif keycode == ord("e"):
                self._logger.info(
                    "Emposs Filter Applying "
                    + ("Started" if not self.applyFilter else "Stoped")
                )
                self._curveFilter = filters.EmpossFilter()
            elif keycode == ord("f"):
                self._logger.info(
                    "Find Edged Filter Applying "
                    + ("Started" if not self.applyFilter else "Stoped")
                )
                self._curveFilter = filters.FindEdgesFilter()
            self.applyFilter = not self.applyFilter
        elif keycode == ord("j"):
            self._logger.info(
                "Object Tracking "
                + ("Started" if not self.shouldTrackingFace else "Stoped")
            )
            self.shouldTracking = not self.shouldTracking
        elif keycode == ord("x"):
            self._logger.info(
                "Face Tracking "
                + ("Started" if not self.shouldTrackingFace else "Stoped")
            )
            self.shouldTrackingFace = not self.shouldTrackingFace
        elif keycode == 27:  # ESC
            self._windowManager.destroyWindow()

class CameoLabelTaker(object):
    def __init__(self, Capture, logger="Cameo", *args, **kwargs):
        self._logger = logging.getLogger(logger)
        self._windowManager = WindowManager("Window", self.onKeypress, (1200, 800))
        self._captureManager = CaptureManager(
            Capture, self._windowManager, False
        )

    def run(self):
        """
        Run Main loop.
        """
        self.rectSize = (400, 400, 200, 200)
        self._windowManager.createWindow()
        self.takeScreenShot = False
        filepath = 'takedImages/p'
        count = 1
        if not os.path.exists(filepath):
            os.makedirs(filepath)
        else:
            for file in os.listdir(filepath):
                if (l := int(file.split('.')[0])) >= count:
                    count = l + 1
        while self._windowManager.isWindowCreated:
            x, y, w, h = self.rectSize
            with self._captureManager as frame:
                if frame is not None:
                    cv2.putText(frame, 'Count For Image: {}'.format(count), (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    if self.takeScreenShot:
                        img = cv2.resize(frame[y:y+h, x:x+w], (24,24))
                        cv2.imwrite(f'{filepath}/{count}.jpg', img)
                        self.takeScreenShot = not self.takeScreenShot
                        cv2.rectangle(frame,(x, y), (x+w, y+h), (0,0,255), 1)
                        count += 1
                    else:
                        cv2.rectangle(frame,(x, y), (x+w, y+h), (255,0,0), 1)
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

        a = 12
        if keycode == 27:  # ESC
            self._windowManager.destroyWindow()
        elif keycode == 84:
            x, y, w, h = self.rectSize
            self.rectSize = (x, y+a, w, h)
        elif keycode == 82:
            x, y, w, h = self.rectSize
            self.rectSize = (x, y-a, w, h)
        elif keycode == 83:
            x, y, w, h = self.rectSize
            self.rectSize = (x+a, y, w, h)
        elif keycode == 81:
            x, y, w, h = self.rectSize
            self.rectSize = (x-a, y, w, h)
        elif keycode == ord('g'):
            x, y, w, h = self.rectSize
            self.rectSize = (x, y, w+a, h+a)
        elif keycode == ord('s'):
            x, y, w, h = self.rectSize
            self.rectSize = (x, y, w-a, h-a)
        elif keycode == ord('t'):
            self.takeScreenShot = not self.takeScreenShot


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
        "-i",
        "--image-label",
        dest='label',
        action="store_true",
        help="Enable Client Mode And Accept Frames From CameoServer Has Address Given On 'cap' Parameter",
    )
    parser.add_argument(
        "-c",
        "--client-mode",
        dest='client',
        action="store_true",
        help="Enable Client Mode And Accept Frames From CameoServer Has Address Given On 'cap' Parameter",
    )
    parser.add_argument(
        "-f",
        "--classifier",
        dest='classifier',
        help="The Specific Haarcascade File To Detect Objects",
    )
    parser.add_argument(
        "-s",
        "--server",
        dest='address',
        help="Enable Server Mode To Start Lisining On The Address Given",
    )
    parser.add_argument(
        "-t",
        "--trashold",
        dest="trash",
        default="1.3",
        type=float,
        help="Trashold Value For Cascade classifing",
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
    cap, label, client, classifier, address, trash, log, depth = vars(parser.parse_args()).values()
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
        if classifier:
            Cameo(CVClient(cap), detect=classifier, trashold=trash).run()
        else:
            Cameo(CVClient(cap)).run()
    elif label:
        CameoLabelTaker(cv2.VideoCapture(cap)).run()
    elif address:
        CameoServer(cv2.VideoCapture(cap), address).run()
    elif depth:
        CameoDepth(cv2.VideoCapture(cap)).run()
    else:
        if classifier:
            Cameo(cv2.VideoCapture(cap), detect=classifier, trashold=trash).run()
        else:
            Cameo(cv2.VideoCapture(cap)).run()
