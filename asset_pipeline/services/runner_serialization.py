from __future__ import annotations

from dataclasses import asdict

import cv2
import numpy as np

from asset_pipeline.services.mask_codec import encode_rle_mask
from asset_pipeline.services.semantic_client import box_from_mask
from asset_pipeline.services.semantic_models import PartTrack
from asset_pipeline.services.models import FrameBox
from asset_pipeline.services.semantic_diagnostics import track_summary


def scale_size(size: dict[str, int], scale_x: float, scale_y: float) -> dict[str, int]:
    return {
        "width": int(round(int(size["width"]) * scale_x)),
        "height": int(round(int(size["height"]) * scale_y)),
    }


def scale_rect_dict(rect: dict[str, int], scale_x: float, scale_y: float) -> dict[str, int]:
    return {
        "x": int(round(int(rect["x"]) * scale_x)),
        "y": int(round(int(rect["y"]) * scale_y)),
        "width": int(round(int(rect["width"]) * scale_x)),
        "height": int(round(int(rect["height"]) * scale_y)),
    }


def scale_crop_box(crop_box: dict[str, int], scale_x: float, scale_y: float) -> dict[str, int]:
    return {
        "left": int(round(int(crop_box["left"]) * scale_x)),
        "top": int(round(int(crop_box["top"]) * scale_y)),
        "right": int(round(int(crop_box["right"]) * scale_x)),
        "bottom": int(round(int(crop_box["bottom"]) * scale_y)),
    }


def scale_metadata_frames(frames: list[dict[str, object]], scale_x: float, scale_y: float) -> list[dict[str, object]]:
    return [
        {
            **frame,
            "sourceBox": scale_rect_dict(frame["sourceBox"], scale_x, scale_y),
            "sheetBox": scale_rect_dict(frame["sheetBox"], scale_x, scale_y),
        }
        for frame in frames
    ]


def scale_frame_box(box: FrameBox, scale_x: float, scale_y: float) -> FrameBox:
    return FrameBox(
        box.index,
        int(round(box.x * scale_x)),
        int(round(box.y * scale_y)),
        int(round(box.width * scale_x)),
        int(round(box.height * scale_y)),
        int(round(box.area * scale_x * scale_y)),
        float(box.center_x * scale_x),
        float(box.center_y * scale_y),
    )


def scale_frames(frames: list[FrameBox], scale_x: float, scale_y: float) -> list[FrameBox]:
    if scale_x == 1.0 and scale_y == 1.0:
        return frames
    return [scale_frame_box(frame, scale_x, scale_y) for frame in frames]


def scale_mask(mask: np.ndarray, scale_x: float, scale_y: float) -> np.ndarray:
    if scale_x == 1.0 and scale_y == 1.0:
        return mask
    target_width = max(1, int(round(mask.shape[1] * scale_x)))
    target_height = max(1, int(round(mask.shape[0] * scale_y)))
    return cv2.resize(mask.astype(np.uint8), (target_width, target_height), interpolation=cv2.INTER_NEAREST).astype(
        bool
    )


def scale_part_tracks(tracks: list[PartTrack], scale_x: float, scale_y: float) -> list[PartTrack]:
    if scale_x == 1.0 and scale_y == 1.0:
        return tracks
    scaled: list[PartTrack] = []
    for track in tracks:
        masks = [scale_mask(mask, scale_x, scale_y) for mask in track.masks]
        boxes = [box_from_mask(index, mask) for index, mask in enumerate(masks)]
        frame_metrics = []
        for index, metric in enumerate(track.frame_metrics):
            next_metric = dict(metric)
            next_metric["area"] = int(masks[index].sum()) if index < len(masks) else int(next_metric.get("area", 0))
            if index < len(boxes) and boxes[index] is not None:
                next_metric["centerX"] = round(float(boxes[index].center_x), 4)
                next_metric["centerY"] = round(float(boxes[index].center_y), 4)
            frame_metrics.append(next_metric)
        scaled.append(
            PartTrack(
                id=track.id,
                label=track.label,
                color=track.color,
                mobility=track.mobility,
                persistence=track.persistence,
                confidence=track.confidence,
                masks=masks,
                boxes=boxes,
                warnings=list(track.warnings),
                presence=[bool(np.any(mask)) for mask in masks],
                mask_statuses=list(track.mask_statuses),
                frame_metrics=frame_metrics,
                stabilize_settings=dict(track.stabilize_settings),
            )
        )
    return scaled


def part_tracks_debug_metadata(tracks: list[object]) -> list[dict[str, object]]:
    return [
        {
            "id": track.id,
            "label": track.label,
            "color": "#%02X%02X%02X" % track.color,
            "confidence": round(float(track.confidence), 4),
            "presence": track.presence,
            "warnings": track.warnings,
            "boxes": [asdict(box) if box else None for box in track.boxes],
            "masks": [encode_rle_mask(mask) for mask in track.masks],
            "maskStatuses": list(getattr(track, "mask_statuses", [])),
            "frameMetrics": list(getattr(track, "frame_metrics", [])),
            "trackSummary": track_summary(track),
            "stabilizeSettings": dict(getattr(track, "stabilize_settings", {})),
        }
        for track in tracks
    ]
