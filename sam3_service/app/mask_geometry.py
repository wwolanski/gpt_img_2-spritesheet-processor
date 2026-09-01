from __future__ import annotations

import re

import cv2
import numpy as np

from app.schemas import PartEdit


def clamp_box_xyxy(box: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box[:4]
    return (
        max(0, min(width - 1, int(round(x1)))),
        max(0, min(height - 1, int(round(y1)))),
        max(1, min(width, int(round(x2)))),
        max(1, min(height, int(round(y2)))),
    )


def expand_box_xyxy(box: list[float], width: int, height: int) -> list[float]:
    x1, y1, x2, y2 = box
    pad_x = max(4.0, (x2 - x1) * 0.15)
    pad_y = max(4.0, (y2 - y1) * 0.15)
    return [
        max(0.0, min(float(width - 1), x1 - pad_x)),
        max(0.0, min(float(height - 1), y1 - pad_y)),
        max(1.0, min(float(width), x2 + pad_x)),
        max(1.0, min(float(height), y2 + pad_y)),
    ]


def draw_trimap_disk(trimap: np.ndarray, x: float | None, y: float | None, radius: int, value: int) -> None:
    if x is None or y is None:
        return
    px, py = int(round(x)), int(round(y))
    if py < 0 or py >= trimap.shape[0] or px < 0 or px >= trimap.shape[1]:
        return
    cv2.circle(trimap, (px, py), radius, int(value), thickness=-1)


def latest_bbox_edit(edits: list[PartEdit]) -> list[float] | None:
    for edit in reversed(edits):
        if edit.type == "bbox" and edit.box and len(edit.box) == 4:
            return [float(value) for value in edit.box]
    return None


def points_match_mask(
    mask: np.ndarray,
    positive_points: list[tuple[float | None, float | None]],
    negative_points: list[tuple[float | None, float | None]],
) -> bool:
    if positive_points:
        for x, y in positive_points:
            if not point_in_mask(mask, x, y):
                return False
    for x, y in negative_points:
        if point_in_mask(mask, x, y):
            return False
    return bool(positive_points or negative_points)


def point_in_mask(mask: np.ndarray, x: float | None, y: float | None) -> bool:
    if x is None or y is None:
        return False
    px, py = int(round(x)), int(round(y))
    if py < 0 or py >= mask.shape[0] or px < 0 or px >= mask.shape[1]:
        return False
    return bool(mask[py, px])


def prompt_tokens(text: str) -> set[str]:
    stop = {"a", "an", "the", "and", "or", "of", "part", "sprite", "character"}
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2 and token not in stop}


def box_iou(left: list[float], right: list[float]) -> float:
    if len(left) < 4 or len(right) < 4:
        return 0.0
    lx1, ly1, lx2, ly2 = left[:4]
    rx1, ry1, rx2, ry2 = right[:4]
    ix1, iy1 = max(lx1, rx1), max(ly1, ry1)
    ix2, iy2 = min(lx2, rx2), min(ly2, ry2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    intersection = iw * ih
    left_area = max(0.0, lx2 - lx1) * max(0.0, ly2 - ly1)
    right_area = max(0.0, rx2 - rx1) * max(0.0, ry2 - ry1)
    union = left_area + right_area - intersection
    return float(intersection / union) if union > 0 else 0.0


def box_xyxy_from_mask(mask: np.ndarray) -> list[float]:
    ys, xs = np.where(mask)
    if ys.size == 0:
        return []
    return [float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)]
