from __future__ import annotations

import numpy as np
from PIL import Image


def rembg_installed() -> bool:
    try:
        import rembg  # noqa: F401
    except ImportError:
        return False
    return True


def rembg_mask(rgb: np.ndarray) -> np.ndarray | None:
    if not rembg_installed():
        return None
    from rembg import new_session, remove

    if not hasattr(rembg_mask, "_session"):
        rembg_mask._session = new_session("birefnet-general")  # type: ignore[attr-defined]
    mask_image = remove(
        Image.fromarray(rgb, "RGB"), only_mask=True, session=rembg_mask._session, post_process_mask=True
    )  # type: ignore[attr-defined]
    return np.array(mask_image.convert("L"), dtype=np.uint8)
