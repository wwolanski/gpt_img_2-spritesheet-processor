from __future__ import annotations

import cv2
import numpy as np


def edge_factor(alpha: np.ndarray, radius: float = 5.0) -> np.ndarray:
    foreground = alpha > 0
    if not np.any(foreground):
        return np.zeros_like(alpha, dtype=np.float32)
    distance = cv2.distanceTransform(foreground.astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32)
    factor = np.clip(1.0 - (distance / max(radius, 0.01)), 0.0, 1.0)
    factor *= alpha.astype(np.float32) / 255.0
    return factor


def neutralize_edge_spill(
    rgb: np.ndarray,
    alpha: np.ndarray,
    fields: dict[str, np.ndarray],
    mode: str,
    strength: float,
    darken: float,
) -> np.ndarray:
    if mode == "none":
        return rgb
    cleaned = rgb.astype(np.float32).copy()
    factor = edge_factor(alpha, radius=5.0)
    spill = np.maximum(fields["green"] - (fields["max_rb"] * 1.03 + fields["min_rb"] * 0.08 + 7), 0.0)
    blend = np.clip((spill / 255.0) * strength + factor * darken, 0.0, 1.0)

    cleaned[:, :, 1] -= spill * np.clip(strength * (0.88 + factor), 0.0, 1.6)
    cleaned[:, :, 1] = np.clip(cleaned[:, :, 1], 0.0, 255.0)

    if mode in {"gray", "auto"}:
        gray = (fields["max_rb"] * 0.72 + fields["min_rb"] * 0.28).astype(np.float32)
        for channel in range(3):
            cleaned[:, :, channel] = cleaned[:, :, channel] * (1.0 - blend) + gray * blend
    elif mode == "black":
        for channel in range(3):
            cleaned[:, :, channel] = cleaned[:, :, channel] * (1.0 - blend)

    return np.clip(cleaned, 0.0, 255.0).astype(np.uint8)


def transparentize_edge_spill(
    alpha: np.ndarray,
    fields: dict[str, np.ndarray],
    strength: float,
) -> np.ndarray:
    if strength <= 0:
        return alpha
    factor = edge_factor(alpha, radius=5.0)
    spill = np.maximum(fields["green"] - (fields["max_rb"] * 1.03 + fields["min_rb"] * 0.08 + 7), 0.0)
    cut = np.clip((spill / 255.0) * strength * (0.9 + factor * 0.7), 0.0, 1.0)
    cleaned_alpha = alpha.astype(np.float32) * (1.0 - cut)
    return np.clip(cleaned_alpha, 0.0, 255.0).astype(np.uint8)
