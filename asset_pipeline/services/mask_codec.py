from __future__ import annotations

import base64
from io import BytesIO

import numpy as np
from PIL import Image


def encode_png_base64(rgb: np.ndarray) -> str:
    buffer = BytesIO()
    Image.fromarray(rgb.astype(np.uint8), mode="RGB").save(buffer, format="PNG", compress_level=1)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def decode_rle_mask(encoded: str, width: int, height: int) -> np.ndarray:
    if not encoded:
        return np.zeros((height, width), dtype=bool)
    counts = [int(part) for part in encoded.split(",") if part]
    values: list[int] = []
    value = 0
    for count in counts:
        values.extend([value] * max(0, count))
        value = 1 - value
    total = width * height
    if len(values) < total:
        values.extend([0] * (total - len(values)))
    return np.array(values[:total], dtype=np.uint8).reshape((height, width)).astype(bool)


def encode_rle_mask(mask: np.ndarray) -> str:
    flat = mask.astype(np.uint8).reshape(-1)
    if flat.size == 0:
        return ""
    counts: list[int] = []
    current = 0
    run = 0
    for item in flat:
        value = int(item > 0)
        if value == current:
            run += 1
        else:
            counts.append(run)
            current = value
            run = 1
    counts.append(run)
    return ",".join(str(count) for count in counts)
