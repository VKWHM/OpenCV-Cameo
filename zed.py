import cv2
import numpy
import pyzed.sl as sl


class ZedCameraClass(sl.Camera):
    def __init__(self, logger="ZedCameraClass"):
        super().__init__()
        self._logger = logging.getLogger(logger)
        self._init_params = sl.InitParameters()
        self._init_params.camera_resolution = sl.RESOLUTION.HD720
        self._init_params.camera_fps = 60
        self._init_params.depth_mode = sl.DEPTH_MODE.ULTRA
        self._isOpened = self.open(self._init_params)

    def __del__(self):
        self.close()

    def isOpened(self):
        if self._isOpened == sl.ERROR_CODE.SUCCESS:
            return True
        self._logger.error("Camera Was't Opened")
        return False

    def grab(self):
        if not self._grabed:
            runtimeParams = sl.RuntimeParameters()
            self._grabed = super().grab(runtimeParams) == sl.ERROR_CODE.SUCCESS
        return self._grabed

    def retrieve(self, channel=sl.VIEW.LEFT):
        if not channel in dir(sl.VIEW):
            self._logger.error("Invalid output type was givin")
            raise ValueError("Invalid output type")
        if self._grabed:
            image = sl.Mat()
            self.retrieve_image(image, channel)
            image_cv2 = cv2.cvtColor(image.get_data(), cv2.COLOR_RGBA2RGB)
            self._grabed = None
            return True, image_cv2
        self._logger.debug("Can't retrieve. Frame don't grabbed")
        return False, numpy.empty([0, 0], dtype=numpy.uint8)

    def read(self):
        self.grab()
        return self.retrieve()

    def get(self, propID):
        if propID in [prop for prop in dir(cv2) if prop.startswith("CAP_PROP")]:
            if propID == cv2.CAP_PROP_FPS:
                return self.getCameraFPS()
            elif propID == cv2.CAP_PROP_FRAME_WIDTH:
                return self.getResolution().width
            elif propID == cv2.CAP_PROP_FRAME_HEIGHT:
                return self.getResolution().height
            else:
                self._logger.debug("Can't found PROP ID")
                return None
        self._logger.error("Invalid PROP ID was givin")
        raise ValueError("Invalid PROP ID")

    def compute_depth_map(self):
        depth = sl.Mat()
        err = self.retrieve_measure(depth, sl.MEASURE.DEPTH)
        if err != sl.ERROR_CODE.SUCCESS:
            self._logger.debug("Depth map wasn't retrieved")
            return None
        return depth

    def release(self):
        if self._isOpened:
            self.close()
            self._isOpened = False

    def distance(self, x, y):
        depth = self.compute_depth_map()
        if depth is not None:
            depth_np = depth.get_data()
            return depth_np[y,x] / 1000.0
        return None
