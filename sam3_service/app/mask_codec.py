from __future__ import annotations

import base64
from io import BytesIO

import numpy as np
from PIL import Image


def decode_png_base64(encoded: str) -> np.ndarray:
    raw = base64.b64decode(encoded)
    return np.array(Image.open(BytesIO(raw)).convert("RGB"), dtype=np.uint8)


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
