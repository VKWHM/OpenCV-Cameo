import cv2
import utils
import logging


class Face(object):
    def __init__(self):
        self.faceRect = None
        self.leftEyeRect = None
        self.rightEyeRect = None


class FaceTracker(object):
    def __init__(
        self,
        scaleFactor=1.3,
        minNeighbors=2,
        flags=cv2.CASCADE_SCALE_IMAGE,
        logger="FaceTracker",
    ):
        self._logger = logging.getLogger(logger)
        self._logger.debug(f"Initial Class {logger=}")
        self.eyeClassifier = cv2.CascadeClassifier("HaarCascades/haarcascade_eye.xml")
        self.faceClassifier = cv2.CascadeClassifier(
            "HaarCascades/haarcascade_frontalface_default.xml"
        )
        self.scaleFactor = scaleFactor
        self.minNeighbors = minNeighbors
        self.flags = flags
        self._faces = []

    @property
    def faces(self):
        return self._faces

    def update(self, image):
        self._faces = []
        if utils.isGray(image):
            image = cv2.equalizeHist(image)
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            image = cv2.equalizeHist(gray)
        minSize = utils.WHDividedBy(image, 8)
        facesRect = self.faceClassifier.detectMultiScale(
            image, self.scaleFactor, self.minNeighbors, self.flags, minSize
        )
        if facesRect is not None:
            for faceRect in facesRect:
                face = Face()
                face.faceRect = faceRect
                x, y, w, h = faceRect
                self._logger.debug(f"x: {x}, y: {y} face detected")
                searchRect = (x, y, w, h)
                lEyeRect = self._detectOneObject(
                    self.eyeClassifier, image, searchRect, 64
                )
                if lEyeRect:
                    self._logger.debug(f"Left eye detected")
                face.leftEyeRect = lEyeRect
                searchRect = (x, y, w, h)
                rEyeRect = self._detectOneObject(
                    self.eyeClassifier, image, searchRect, 64
                )
                if rEyeRect:
                    self._logger.debug(f"Right eye detected")
                face.rightEyeRect = rEyeRect
                self._faces.append(face)
            return True
        else:
            return False

    def _detectOneObject(self, classifier, image, searchRect, imageSizeToMinSizeRatio):
        minSize = utils.WHDividedBy(image, imageSizeToMinSizeRatio)
        x, y, w, h = searchRect
        image = image[x : x + w, y : y + h]
        objectRect = classifier.detectMultiScale(
            image, self.scaleFactor, self.minNeighbors, self.flags, minSize
        )
        if len(objectRect) == 0:
            return
        subx, suby, subw, subh = objectRect[0]
        return (x + subx, y + suby, subw, subh)

    def drawDebugRects(self, image):
        def check(x):
            return getattr(face, x) is not None

        if utils.isGray(image):
            colors = {"faceRect": 255, "leftEyeRect": 255, "rightEyeRect": 255}
        else:
            colors = {
                "faceRect": (255, 255, 255),
                "leftEyeRect": (0, 0, 255),
                "rightEyeRect": (0, 255, 255),
            }

        for face in self._faces:
            for attribute in list(
                filter(check, [x for x in dir(face) if not x.startswith("_")])
            ):
                utils.outlineRect(
                    image, getattr(face, attribute), colors.get(attribute, 255)
                )

