from __future__ import annotations

import numpy as np


def synthetic_spritesheet() -> np.ndarray:
    """Return a tiny two-frame RGB spritesheet with a chroma-key background."""

    image = np.zeros((72, 144, 3), dtype=np.uint8)
    image[:, :] = (0, 255, 0)

    # Two separated, deliberately asymmetric shapes make frame ordering and
    # alpha extraction observable without depending on a checked-in binary.
    image[16:54, 12:42] = (190, 65, 45)
    image[24:44, 42:48] = (190, 65, 45)
    image[14:56, 88:118] = (55, 75, 205)
    image[20:50, 82:88] = (55, 75, 205)
    return image
