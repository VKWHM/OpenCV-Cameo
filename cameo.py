import cv2
import logging
import filters
try:
	import colorlog
except ImportError:
	import sys
	sys.stderr.write('colorlog Module Is Not Installed !!\n')
	sys.exit(1)
	
from manager import CaptureManager, WindowManager


class Cameo(object):
	def __init__(self):
		self._windowManager = WindowManager('Window', self.onKeypress)
		self._captureManager = CaptureManager(cv2.VideoCapture('test.mp4'), self._windowManager, True)
		self._curveFilter = filters.SharpenFilter()

	def run(self):
		"""
		Run Main loop.
		"""
		self._windowManager.createWindow()
		while self._windowManager.isWindowCreated:
			with self._captureManager as frame:
				if frame is not None:
					#filters.strokeEdges(frame, frame, edgeKsize=5)
					self._curveFilter.apply(frame, frame)
			self._windowManager.processEvent()
		return 
		
	def onKeypress(self, keycode):
		"""
		Handle a keypress.
		space -> Take a screenshot
		tab -> Start/Stop recording a screencast.
		escape -> Quit.
		"""
		if keycode == 32: # space
			self._captureManager.writeImage('screenshot.png')
		elif keycode == 9: # TAB
			if not self._captureManager.isWritingVideo:
				self._captureManager.startWritingVideo('screencast.mp4', cv2.VideoWriter_fourcc(*'MP4V'))
			else:
				self._captureManager.stopWritingVideo()
		elif keycode == 27: # ESC
			self._windowManager.destroyWindow()


class CameoDepth(Cameo):
	def __init__(self, loggerName = 'CameoDepth'):
		self._windowManager = WindowManager('Cameo', self.onKeypress)
		#device = cv2.CAP_OPENNI2_ASUS
		device = cv2.CAP_OPENNI2
		self._captureManager = CaptureManager(cv2.VideoCapture(device), self._windowManager, True, True)
		self._curveFilter = filters.SharpenFilter()
		self._logger = logging.getLogger(loggerName)
		self._logger.debug(f'Initial Class {loggerName=}')

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
				self._logger.debug("BGR frame faild, try to capture an infrared frame instead")
				self._captureManager.channel = cv2.CAP_OPENNI_IR_IMAGE
				frame = self._captureManager.frame
			if frame is not None:
				mask = depth.createMedianMask(disparityMap, validDepthMask)
				frame[mask == 0] = 0
				if self._captureManager.channel == cv2.CAP_OPENNI_BGR_IMAGE:
					self._curveFilter.apply(frame,frame)
			self._captureManager.exitFrame()
			self._windowManager.processEvent()

if __name__ == '__main__':
	colorlog.basicConfig(format="[%(asctime)s.%(msecs)03d] [%(log_color)s%(levelname)s%(reset)s] (%(name)s): %(log_color)s%(message)s%(reset)s", level=logging.DEBUG, datefmt='%H:%M:%S')
	#Cameo().run()
	CameoDepth().run()
