from __future__ import annotations

import cv2
import numpy as np

from asset_pipeline.services.image_ops import bool_to_uint8, dilate, erode, round4
from asset_pipeline.services.models import FrameBox, Metrics


def evaluate_metrics(rgba: np.ndarray, _key: tuple[int, int, int], frames: list[FrameBox], profile: str) -> Metrics:
    alpha = rgba[:, :, 3].astype(np.uint8)
    rgb = rgba[:, :, :3].astype(np.float32)
    border_alpha = np.concatenate([alpha[0, :], alpha[-1, :], alpha[:, 0], alpha[:, -1]])
    visible = alpha > 10
    edge = dilate(visible, 3) & ~erode(visible, 3)
    max_rb = np.maximum(rgb[:, :, 0], rgb[:, :, 2])
    green_spill = (rgb[:, :, 1] > max_rb + 12) & edge & visible
    semi = (alpha > 0) & (alpha < 255)

    component_count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(bool_to_uint8(visible), 8)
    median_area = float(np.median([frame.area for frame in frames]))
    tiny_components = 0
    for component_index in range(1, component_count):
        area = int(stats[component_index, cv2.CC_STAT_AREA])
        if area < max(48, median_area * 0.02):
            tiny_components += 1

    border_leak_ratio = float((border_alpha > 12).mean())
    green_spill_ratio = float(green_spill.mean()) if np.any(edge & visible) else 0.0
    edge_alpha_ratio = float(semi.mean())
    opaque_coverage = float((alpha >= 245).mean())

    score = 100.0
    score -= border_leak_ratio * 2600.0
    score -= green_spill_ratio * 2200.0
    score -= tiny_components * 2.0
    if profile == "pixelart":
        score -= edge_alpha_ratio * 220.0
    if profile == "thick-outline":
        dark_ratio = (
            float(((rgb[:, :, 0] < 42) & (rgb[:, :, 1] < 42) & (rgb[:, :, 2] < 42) & edge).mean())
            if np.any(edge)
            else 0.0
        )
        score += dark_ratio * 180.0

    return Metrics(
        score=round4(score),
        border_leak_ratio=round4(border_leak_ratio),
        green_spill_ratio=round4(green_spill_ratio),
        edge_alpha_ratio=round4(edge_alpha_ratio),
        tiny_component_count=int(tiny_components),
        component_count=len(frames),
        opaque_coverage=round4(opaque_coverage),
    )
