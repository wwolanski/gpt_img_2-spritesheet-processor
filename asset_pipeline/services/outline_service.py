from __future__ import annotations

import cv2
import numpy as np

from asset_pipeline.services.image_ops import bool_to_uint8, dilate, erode


def derive_dark_edge_color(rgb: np.ndarray, alpha: np.ndarray) -> tuple[int, int, int]:
    visible = alpha > 24
    edge = dilate(visible, 3) & ~erode(visible, 3)
    sample = rgb[edge]
    if sample.size == 0:
        return (18, 18, 18)
    luminance = sample[:, 0] * 0.299 + sample[:, 1] * 0.587 + sample[:, 2] * 0.114
    threshold = np.percentile(luminance, 30)
    dark_sample = sample[luminance <= threshold]
    if dark_sample.size == 0:
        dark_sample = sample
    median = np.median(dark_sample, axis=0)
    clipped = np.clip(median * 0.72, 0, 255).astype(np.uint8)
    return (int(clipped[0]), int(clipped[1]), int(clipped[2]))


def compose_outline(
    rgb: np.ndarray,
    alpha: np.ndarray,
    width: int,
    opacity: float,
    blur: float,
    color: tuple[int, int, int],
) -> tuple[np.ndarray, np.ndarray]:
    if width <= 0 or opacity <= 0:
        return rgb, alpha
    visible = alpha > 0
    outline_mask = dilate(visible, width * 2 + 1) & ~visible
    outline_alpha = bool_to_uint8(outline_mask).astype(np.float32) * opacity
    if blur > 0:
        outline_alpha = cv2.GaussianBlur(outline_alpha, (0, 0), blur)

    expanded_alpha = np.maximum(alpha.astype(np.float32), outline_alpha)
    expanded_rgb = rgb.astype(np.float32).copy()
    outline_factor = np.clip(outline_alpha / 255.0, 0.0, 1.0)
    source_factor = alpha.astype(np.float32) / np.maximum(expanded_alpha, 1.0)
    for channel, value in enumerate(color):
        expanded_rgb[:, :, channel] = expanded_rgb[:, :, channel] * source_factor + value * outline_factor * (
            1.0 - source_factor
        )

    return np.clip(expanded_rgb, 0, 255).astype(np.uint8), np.clip(expanded_alpha, 0, 255).astype(np.uint8)
