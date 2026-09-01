from __future__ import annotations

from collections import Counter

import cv2
import numpy as np
from PIL import Image


def round4(value: float) -> float:
    return round(float(value), 4)


def quantized_mode_key(image: Image.Image) -> tuple[int, int, int]:
    rgb = np.array(image.convert("RGB"), dtype=np.uint8)
    border = np.concatenate([rgb[0, :, :], rgb[-1, :, :], rgb[:, 0, :], rgb[:, -1, :]], axis=0)
    quantized = (border // 8) * 8
    counter = Counter(tuple(int(channel) for channel in pixel) for pixel in quantized)
    return counter.most_common(1)[0][0]


def connected_to_border(candidate: np.ndarray) -> np.ndarray:
    # OpenCV flood fill runs in native code; this replaces a Python pixel queue.
    height, width = candidate.shape
    source = bool_to_uint8(candidate)
    mask = np.zeros((height + 2, width + 2), dtype=np.uint8)

    for x in range(width):
        if source[0, x] == 255:
            cv2.floodFill(source, mask, (x, 0), 128)
        if source[height - 1, x] == 255:
            cv2.floodFill(source, mask, (x, height - 1), 128)

    for y in range(height):
        if source[y, 0] == 255:
            cv2.floodFill(source, mask, (0, y), 128)
        if source[y, width - 1] == 255:
            cv2.floodFill(source, mask, (width - 1, y), 128)

    return source == 128


def bool_to_uint8(mask: np.ndarray) -> np.ndarray:
    return np.where(mask, 255, 0).astype(np.uint8)


def morph(mask: np.ndarray, operation: int, size: int, iterations: int = 1) -> np.ndarray:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    result = cv2.morphologyEx(bool_to_uint8(mask), operation, kernel, iterations=iterations)
    return result > 0


def dilate(mask: np.ndarray, size: int, iterations: int = 1) -> np.ndarray:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    result = cv2.dilate(bool_to_uint8(mask), kernel, iterations=iterations)
    return result > 0


def erode(mask: np.ndarray, size: int, iterations: int = 1) -> np.ndarray:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    result = cv2.erode(bool_to_uint8(mask), kernel, iterations=iterations)
    return result > 0


def rgb_hsv_fields(rgb: np.ndarray) -> dict[str, np.ndarray]:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    red = rgb[:, :, 0].astype(np.float32)
    green = rgb[:, :, 1].astype(np.float32)
    blue = rgb[:, :, 2].astype(np.float32)
    return {
        "rgb": rgb.astype(np.float32),
        "red": red,
        "green": green,
        "blue": blue,
        "hue": hsv[:, :, 0].astype(np.float32),
        "sat": hsv[:, :, 1].astype(np.float32),
        "val": hsv[:, :, 2].astype(np.float32),
        "max_rb": np.maximum(red, blue),
        "min_rb": np.minimum(red, blue),
    }


def crop_to_alpha(rgba: np.ndarray, padding: int) -> tuple[np.ndarray, dict[str, int]]:
    alpha = rgba[:, :, 3]
    nonzero = np.argwhere(alpha > 0)
    if nonzero.size == 0:
        return rgba, {"left": 0, "top": 0, "right": rgba.shape[1], "bottom": rgba.shape[0]}
    top = max(0, int(nonzero[:, 0].min()) - padding)
    left = max(0, int(nonzero[:, 1].min()) - padding)
    bottom = min(rgba.shape[0], int(nonzero[:, 0].max()) + 1 + padding)
    right = min(rgba.shape[1], int(nonzero[:, 1].max()) + 1 + padding)
    return rgba[top:bottom, left:right, :], {"left": left, "top": top, "right": right, "bottom": bottom}


def crop_with_box(rgba: np.ndarray, crop_box: dict[str, int]) -> np.ndarray:
    return rgba[crop_box["top"] : crop_box["bottom"], crop_box["left"] : crop_box["right"], :]


def save_png(path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image).save(path, compress_level=1)
