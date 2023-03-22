import cv2


def isGray(image):
    return image.ndim < 3


def WHDividedBy(image, divisor):
    h, w = image.shape[:2]
    return (w // divisor, h // divisor)


def outlineRect(image, Rect, Color):
    if Rect is not None:
        x, y, w, h = Rect
        cv2.rectangle(image, (x, y), (x + w, y + h), Color, 5)

