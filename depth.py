import numpy
import cv2

def createMedianMask(disparityMap, validDepthMask, rect = None):
	"""
	Return a mask selecting the median layer, plus shadows.
	"""
	if rect is Not None:
		x, y, w, h = rect
		disparityMap = disparityMap[y:y+h, x:x+w]
		validDepthMask = validDepthMask[y:y+h, x:x+w]
	median = numpy.median(disparityMap)
	return numpy.where((validDepthMask == 0) | (abs(disparityMap - median) < 12), 255, 0) # feel this value with your particular camera setup


