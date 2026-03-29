"""Image preprocessing for OCR quality improvement."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Deskew image using Hough line transform."""
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
    if lines is None:
        return gray

    angles = []
    for line in lines[:60]:
        rho, theta = line[0]
        angle = (theta * 180 / np.pi) - 90
        if -15 < angle < 15:
            angles.append(angle)
    if not angles:
        return gray

    median_angle = float(np.median(angles))
    h, w = gray.shape[:2]
    matrix = cv2.getRotationMatrix2D((w // 2, h // 2), median_angle, 1.0)
    return cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def _crop_borders(binary: np.ndarray) -> np.ndarray:
    """Remove large white borders around document body."""
    coords = cv2.findNonZero(255 - binary)
    if coords is None:
        return binary
    x, y, w, h = cv2.boundingRect(coords)
    return binary[y : y + h, x : x + w]


def preprocess_image(pil_image: Image.Image) -> Image.Image:
    """Apply grayscale, deskew, denoise, Otsu binarization and border crop."""
    img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    deskewed = _deskew(gray)
    denoised = cv2.GaussianBlur(deskewed, (5, 5), 0)
    _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cropped = _crop_borders(binary)
    return Image.fromarray(cropped)
