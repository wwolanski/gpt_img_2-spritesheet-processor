from __future__ import annotations


import cv2
import numpy as np

from asset_pipeline.services.image_ops import bool_to_uint8, morph
from asset_pipeline.services.models import FrameBox


def detect_frames(alpha: np.ndarray, min_frame_area: int, alpha_cutoff: int) -> list[FrameBox]:
    mask = alpha > alpha_cutoff
    if not np.any(mask):
        return [
            FrameBox(
                0,
                0,
                0,
                alpha.shape[1],
                alpha.shape[0],
                int(alpha.shape[0] * alpha.shape[1]),
                alpha.shape[1] / 2,
                alpha.shape[0] / 2,
            )
        ]

    closed = morph(mask, cv2.MORPH_CLOSE, 3, iterations=1)
    component_count, _labels, stats, centroids = cv2.connectedComponentsWithStats(bool_to_uint8(closed), 8)
    frames: list[FrameBox] = []
    for component_index in range(1, component_count):
        x, y, width, height, area = (int(stats[component_index, index]) for index in range(5))
        if area < min_frame_area:
            continue
        frames.append(
            FrameBox(
                len(frames),
                x,
                y,
                width,
                height,
                area,
                float(centroids[component_index][0]),
                float(centroids[component_index][1]),
            )
        )

    if not frames:
        return [
            FrameBox(
                0,
                0,
                0,
                alpha.shape[1],
                alpha.shape[0],
                int(alpha.shape[0] * alpha.shape[1]),
                alpha.shape[1] / 2,
                alpha.shape[0] / 2,
            )
        ]

    row_tolerance = max(24.0, float(np.median([frame.height for frame in frames])) * 0.45)
    rows: list[list[FrameBox]] = []
    for frame in sorted(frames, key=lambda item: (item.center_y, item.x)):
        for row in rows:
            row_center = sum(item.center_y for item in row) / len(row)
            if abs(frame.center_y - row_center) <= row_tolerance:
                row.append(frame)
                break
        else:
            rows.append([frame])

    ordered: list[FrameBox] = []
    for row in sorted(rows, key=lambda items: min(item.y for item in items)):
        for frame in sorted(row, key=lambda item: item.x):
            frame.index = len(ordered)
            ordered.append(frame)
    split = split_wide_frames(mask, ordered, min_frame_area)
    for index, frame in enumerate(split):
        frame.index = index
    return split


def split_wide_frames(mask: np.ndarray, frames: list[FrameBox], min_frame_area: int) -> list[FrameBox]:
    if len(frames) < 2:
        return frames
    median_width = float(np.median([frame.width for frame in frames]))
    rebuilt: list[FrameBox] = []
    for frame in frames:
        if frame.width <= median_width * 1.45:
            rebuilt.append(frame)
            continue

        submask = mask[frame.y : frame.y + frame.height, frame.x : frame.x + frame.width]
        column_energy = submask.sum(axis=0)
        threshold = max(2, int(submask.shape[0] * 0.06))
        low = column_energy <= threshold
        segments: list[tuple[int, int]] = []
        start = 0
        run_start: int | None = None
        for index, is_low in enumerate(low):
            if is_low and run_start is None:
                run_start = index
            if not is_low and run_start is not None:
                if (
                    index - run_start >= 3
                    and run_start > median_width * 0.3
                    and (frame.width - index) > median_width * 0.3
                ):
                    split_point = (run_start + index) // 2
                    segments.append((start, split_point))
                    start = split_point
                run_start = None
        segments.append((start, frame.width))

        if len(segments) == 1:
            split_points = projection_split_points(column_energy, median_width)
            if split_points:
                segments = []
                start = 0
                for split_point in split_points:
                    segments.append((start, split_point))
                    start = split_point
                segments.append((start, frame.width))

        if len(segments) == 1:
            rebuilt.append(frame)
            continue

        for left, right in segments:
            if right - left <= max(24, median_width * 0.28):
                continue
            part_mask = submask[:, left:right]
            ys, xs = np.where(part_mask)
            if ys.size == 0:
                continue
            x0 = frame.x + left + int(xs.min())
            y0 = frame.y + int(ys.min())
            x1 = frame.x + left + int(xs.max()) + 1
            y1 = frame.y + int(ys.max()) + 1
            area = (x1 - x0) * (y1 - y0)
            if area < min_frame_area:
                continue
            rebuilt.append(FrameBox(frame.index, x0, y0, x1 - x0, y1 - y0, area, (x0 + x1) / 2, (y0 + y1) / 2))
    return rebuilt


def projection_split_points(column_energy: np.ndarray, median_width: float) -> list[int]:
    if column_energy.size < max(48, median_width * 1.5):
        return []
    kernel = np.array([1, 2, 3, 4, 3, 2, 1], dtype=np.float32)
    kernel /= kernel.sum()
    smooth = np.convolve(column_energy.astype(np.float32), kernel, mode="same")
    threshold = max(6.0, float(np.median(smooth)) * 0.58)
    candidate_indexes: list[int] = []
    edge_margin = int(max(18, median_width * 0.28))
    for index in range(edge_margin, len(smooth) - edge_margin):
        value = smooth[index]
        if value > threshold:
            continue
        neighborhood = smooth[max(0, index - 6) : min(len(smooth), index + 7)]
        if value != np.min(neighborhood):
            continue
        if candidate_indexes and index - candidate_indexes[-1] < max(18, median_width * 0.18):
            if value < smooth[candidate_indexes[-1]]:
                candidate_indexes[-1] = index
            continue
        candidate_indexes.append(index)
    return candidate_indexes


def expand_frames(frames: list[FrameBox], width: int, height: int, padding: int) -> list[FrameBox]:
    expanded: list[FrameBox] = []
    for frame in frames:
        left = max(0, frame.x - padding)
        top = max(0, frame.y - padding)
        right = min(width, frame.x + frame.width + padding)
        bottom = min(height, frame.y + frame.height + padding)
        expanded.append(
            FrameBox(
                frame.index,
                left,
                top,
                right - left,
                bottom - top,
                (right - left) * (bottom - top),
                (left + right) / 2,
                (top + bottom) / 2,
            )
        )
    return expanded


def frame_anchor(crop: np.ndarray) -> tuple[float, float]:
    alpha = crop[:, :, 3]
    ys, xs = np.where(alpha > 10)
    if ys.size == 0:
        return crop.shape[1] / 2, crop.shape[0]
    return float(xs.mean()), float(ys.max() + 1)


def normalized_frame_layout(
    rgba: np.ndarray,
    frames: list[FrameBox],
    frame_padding: int,
    stabilize_geometry: bool = True,
) -> tuple[dict[str, int], list[tuple[int, int]]]:
    crops = [rgba[frame.y : frame.y + frame.height, frame.x : frame.x + frame.width, :] for frame in frames]
    if stabilize_geometry:
        anchors = [frame_anchor(crop) for crop in crops]
        left_extent = max(anchor_x for anchor_x, _anchor_y in anchors)
        right_extent = max(crop.shape[1] - anchor_x for crop, (anchor_x, _anchor_y) in zip(crops, anchors))
        top_extent = max(anchor_y for _anchor_x, anchor_y in anchors)
        bottom_extent = max(crop.shape[0] - anchor_y for crop, (_anchor_x, anchor_y) in zip(crops, anchors))
        target_anchor_x = frame_padding + int(np.ceil(left_extent))
        target_anchor_y = frame_padding + int(np.ceil(top_extent))
        canvas_width = frame_padding * 2 + int(np.ceil(left_extent)) + int(np.ceil(right_extent))
        canvas_height = frame_padding * 2 + int(np.ceil(top_extent)) + int(np.ceil(bottom_extent))
        offsets = [
            (int(round(target_anchor_x - anchor_x)), int(round(target_anchor_y - anchor_y)))
            for anchor_x, anchor_y in anchors
        ]
    else:
        global_top = min(frame.y for frame in frames)
        global_bottom = max(frame.y + frame.height for frame in frames)
        canvas_width = max(frame.width for frame in frames) + frame_padding * 2
        canvas_height = (global_bottom - global_top) + frame_padding * 2
        offsets = [
            (
                frame_padding + (canvas_width - frame_padding * 2 - frame.width) // 2,
                frame_padding + (frame.y - global_top),
            )
            for frame in frames
        ]
    return {"width": canvas_width, "height": canvas_height}, offsets


def build_normalized_sheet(
    rgba: np.ndarray,
    frames: list[FrameBox],
    frame_padding: int,
    stabilize_geometry: bool = True,
) -> tuple[np.ndarray, list[dict[str, object]], dict[str, int]]:
    crops = [rgba[frame.y : frame.y + frame.height, frame.x : frame.x + frame.width, :] for frame in frames]
    normalized_size, offsets = normalized_frame_layout(rgba, frames, frame_padding, stabilize_geometry)
    canvas_width = normalized_size["width"]
    canvas_height = normalized_size["height"]
    sheet = np.zeros((canvas_height, canvas_width * len(frames), 4), dtype=np.uint8)
    metadata_frames: list[dict[str, object]] = []

    for frame, crop, (local_x, offset_y) in zip(frames, crops, offsets):
        offset_x = frame.index * canvas_width + local_x
        sheet[offset_y : offset_y + frame.height, offset_x : offset_x + frame.width, :] = crop
        metadata_frames.append(
            {
                "index": frame.index,
                "sourceBox": {"x": frame.x, "y": frame.y, "width": frame.width, "height": frame.height},
                "sheetBox": {
                    "x": frame.index * canvas_width,
                    "y": 0,
                    "width": canvas_width,
                    "height": canvas_height,
                },
            }
        )

    return sheet, metadata_frames, {"width": canvas_width, "height": canvas_height}


def build_sheet_from_crops(
    crops: list[np.ndarray],
) -> tuple[np.ndarray, list[dict[str, object]], dict[str, int], list[FrameBox]]:
    if not crops:
        raise ValueError("At least one frame crop is required.")
    canvas_height, canvas_width = crops[0].shape[:2]
    if any(crop.shape[:2] != (canvas_height, canvas_width) for crop in crops):
        raise ValueError("Interpolated frame crops must share one normalized size.")
    sheet = np.concatenate(crops, axis=1)
    metadata_frames: list[dict[str, object]] = []
    sheet_frames: list[FrameBox] = []
    for index, crop in enumerate(crops):
        alpha = crop[:, :, 3]
        area = int(np.count_nonzero(alpha))
        metadata_frames.append(
            {
                "index": index,
                "sourceBox": {"x": 0, "y": 0, "width": canvas_width, "height": canvas_height},
                "sheetBox": {"x": index * canvas_width, "y": 0, "width": canvas_width, "height": canvas_height},
            }
        )
        sheet_frames.append(
            FrameBox(
                index,
                index * canvas_width,
                0,
                canvas_width,
                canvas_height,
                area,
                index * canvas_width + canvas_width / 2,
                canvas_height / 2,
            )
        )
    return sheet, metadata_frames, {"width": canvas_width, "height": canvas_height}, sheet_frames
