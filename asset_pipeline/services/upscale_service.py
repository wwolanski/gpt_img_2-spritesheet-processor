from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image


def upscale_rgba(rgba: np.ndarray, mode: str, aura_model: str) -> np.ndarray:
    if mode == "none":
        return rgba
    pil_rgba = Image.fromarray(rgba, "RGBA")
    if mode == "nearest-2x":
        return np.array(
            pil_rgba.resize((pil_rgba.width * 2, pil_rgba.height * 2), Image.Resampling.NEAREST), dtype=np.uint8
        )
    if mode == "nearest-4x":
        return np.array(
            pil_rgba.resize((pil_rgba.width * 4, pil_rgba.height * 4), Image.Resampling.NEAREST), dtype=np.uint8
        )
    if mode == "aura-sr":
        try:
            aura = _load_aura_model(aura_model)
        except ImportError as error:  # pragma: no cover
            raise RuntimeError(
                "AuraSR requested but package not installed. Run: .venv/bin/python -m pip install -r asset_pipeline/requirements.txt"
            ) from error
        alpha = pil_rgba.getchannel("A")
        rgb = Image.new("RGB", pil_rgba.size, (0, 0, 0))
        rgb.paste(pil_rgba.convert("RGB"), mask=alpha)
        upscaled_rgb = aura.upscale_4x_overlapped(rgb)
        upscaled_alpha = alpha.resize(upscaled_rgb.size, Image.Resampling.LANCZOS)
        result = upscaled_rgb.convert("RGBA")
        result.putalpha(upscaled_alpha)
        return np.array(result, dtype=np.uint8)
    raise ValueError(f"Unsupported upscale mode: {mode}")


@lru_cache(maxsize=4)
def _load_aura_model(aura_model: str):
    from aura_sr import AuraSR

    return AuraSR.from_pretrained(aura_model)


def clear_aura_model_cache() -> None:
    """Release cached AuraSR model references, primarily for controlled shutdown/tests."""

    _load_aura_model.cache_clear()
