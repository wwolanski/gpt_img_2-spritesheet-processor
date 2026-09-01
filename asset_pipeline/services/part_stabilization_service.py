from __future__ import annotations


import cv2
import numpy as np

from asset_pipeline.services.image_ops import bool_to_uint8, dilate, round4
from asset_pipeline.services.semantic_client import box_from_mask
from asset_pipeline.services.semantic_diagnostics import (
    compute_semantic_metrics,
    mask_iou,
)
from asset_pipeline.services.semantic_models import FrameSequence, PartTrack, SemanticMetrics


def validate_part_tracks(tracks: list[PartTrack], sequence: FrameSequence) -> list[PartTrack]:
    validated: list[PartTrack] = []
    for track in tracks:
        validate_single_track(track, sequence)
        validated.append(track)
    reject_cross_track_conflicts(validated)
    return merge_duplicate_tracks(validated)


def validate_single_track(track: PartTrack, sequence: FrameSequence) -> None:
    alpha_masks = [dilate(alpha > 10, 3) for alpha in sequence.base_alpha_frames]
    clipped_masks: list[np.ndarray] = []
    component_lists: list[list[dict[str, object]]] = []
    seed_areas: list[float] = []
    seed_centers: list[tuple[float, float]] = []

    for index, mask in enumerate(track.masks):
        alpha_mask = alpha_masks[index]
        resized = resize_mask(mask, alpha_mask.shape)
        clipped = resized & alpha_mask
        clipped_masks.append(clipped)
        components = mask_components(clipped)
        component_lists.append(components)
        valid_components = [
            item for item in components if track.id == "body" or item["area"] / max(1, int(alpha_mask.sum())) <= 0.85
        ]
        if valid_components:
            seed = max(valid_components, key=lambda item: item["area"])
            seed_areas.append(float(seed["area"]))
            seed_centers.append((float(seed["center_x"]), float(seed["center_y"])))

    median_area = float(np.median(seed_areas)) if seed_areas else 0.0
    median_center = (
        (
            float(np.median([center[0] for center in seed_centers])),
            float(np.median([center[1] for center in seed_centers])),
        )
        if seed_centers
        else None
    )

    next_masks: list[np.ndarray] = []
    statuses: list[str] = []
    metrics: list[dict[str, object]] = []
    for index, components in enumerate(component_lists):
        alpha_mask = alpha_masks[index]
        silhouette_area = max(1, int(alpha_mask.sum()))
        metric: dict[str, object] = {
            "frame": index,
            "componentCount": len(components),
            "silhouetteArea": silhouette_area,
        }
        if not components:
            next_masks.append(np.zeros_like(alpha_mask, dtype=bool))
            statuses.append("missing")
            metric.update({"status": "missing", "area": 0, "silhouetteRatio": 0.0})
            metrics.append(metric)
            continue

        if track.id == "body":
            selected_mask = clipped_masks[index]
            selected = {
                "area": int(selected_mask.sum()),
                "center_x": float(box_from_mask(index, selected_mask).center_x) if np.any(selected_mask) else 0.0,
                "center_y": float(box_from_mask(index, selected_mask).center_y) if np.any(selected_mask) else 0.0,
            }
        else:
            selected = choose_component(components, median_area, median_center, alpha_mask.shape, track.mobility)
            selected_mask = selected["mask"]

        area = int(selected_mask.sum())
        silhouette_ratio = float(area / silhouette_area)
        area_ratio = float(area / max(1.0, median_area)) if median_area > 0 else 1.0
        metric.update(
            {
                "area": area,
                "areaRatio": round4(area_ratio),
                "silhouetteRatio": round4(silhouette_ratio),
                "centerX": round4(float(selected.get("center_x", 0.0))),
                "centerY": round4(float(selected.get("center_y", 0.0))),
            }
        )

        status = "accepted"
        if track.id != "body" and silhouette_ratio > 0.85:
            status = "rejected_wrong_part"
            track.warnings.append(f"frame {index} rejected: mask covers >85% silhouette")
            selected_mask = np.zeros_like(alpha_mask, dtype=bool)
        elif track.id != "body" and median_area > 0 and not area_ratio_allowed(area_ratio, track.mobility):
            status = "rejected_jump"
            track.warnings.append(
                f"frame {index} rejected: area ratio {area_ratio:.2f} outside {track.mobility} limits"
            )
            selected_mask = np.zeros_like(alpha_mask, dtype=bool)
        elif track.id != "body" and median_center is not None:
            center_dist = float(
                np.linalg.norm(np.array([selected["center_x"], selected["center_y"]]) - np.array(median_center))
            )
            frame_diag = float(np.hypot(alpha_mask.shape[1], alpha_mask.shape[0]))
            metric["centerDistance"] = round4(center_dist)
            if center_dist > center_distance_limit(track.mobility) * frame_diag:
                status = "rejected_jump"
                track.warnings.append(f"frame {index} rejected: centroid jump {center_dist:.1f}px")
                selected_mask = np.zeros_like(alpha_mask, dtype=bool)

        next_masks.append(selected_mask.astype(bool))
        statuses.append(status)
        metric["status"] = status
        metrics.append(metric)

    track.masks = next_masks
    track.boxes = [box_from_mask(index, mask) for index, mask in enumerate(next_masks)]
    track.mask_statuses = statuses
    reject_abrupt_centroid_jumps(track, sequence)
    update_track_presence_and_metrics(track, metrics)


def mask_components(mask: np.ndarray) -> list[dict[str, object]]:
    if not np.any(mask):
        return []
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(bool_to_uint8(mask), 8)
    components: list[dict[str, object]] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area <= 0:
            continue
        item_mask = labels == label
        components.append(
            {
                "mask": item_mask,
                "area": area,
                "x": int(stats[label, cv2.CC_STAT_LEFT]),
                "y": int(stats[label, cv2.CC_STAT_TOP]),
                "width": int(stats[label, cv2.CC_STAT_WIDTH]),
                "height": int(stats[label, cv2.CC_STAT_HEIGHT]),
                "center_x": float(centroids[label][0]),
                "center_y": float(centroids[label][1]),
            }
        )
    return components


def choose_component(
    components: list[dict[str, object]],
    median_area: float,
    median_center: tuple[float, float] | None,
    shape: tuple[int, int],
    mobility: str,
) -> dict[str, object]:
    if len(components) == 1 or median_area <= 0 or median_center is None:
        return max(components, key=lambda item: item["area"])
    diag = max(1.0, float(np.hypot(shape[1], shape[0])))
    center_scale = max(1.0, center_distance_limit(mobility) * diag)

    def score(item: dict[str, object]) -> float:
        area_ratio = float(item["area"]) / max(1.0, median_area)
        area_score = abs(float(np.log(max(0.05, min(20.0, area_ratio)))))
        center_dist = float(np.linalg.norm(np.array([item["center_x"], item["center_y"]]) - np.array(median_center)))
        center_score = center_dist / center_scale
        small_penalty = 1.0 / max(1.0, float(item["area"]))
        return area_score + center_score + small_penalty

    return min(components, key=score)


def area_ratio_allowed(area_ratio: float, mobility: str) -> bool:
    low, high = {
        "static": (0.35, 2.8),
        "low": (0.25, 3.2),
        "medium": (0.18, 4.0),
        "high": (0.12, 5.5),
        "accessory": (0.18, 4.5),
    }.get(mobility, (0.18, 4.0))
    return low <= area_ratio <= high


def center_distance_limit(mobility: str) -> float:
    return {
        "static": 0.22,
        "low": 0.30,
        "medium": 0.45,
        "high": 0.65,
        "accessory": 0.35,
    }.get(mobility, 0.45)


def reject_abrupt_centroid_jumps(track: PartTrack, sequence: FrameSequence) -> None:
    if track.id == "body" or track.mobility in {"medium", "high"}:
        return
    limit = {
        "static": 0.28,
        "low": 0.36,
        "accessory": 0.50,
    }.get(track.mobility, 0.45)
    frame_count = len(track.masks)
    if frame_count < 3:
        return
    for index, box in enumerate(track.boxes):
        if box is None or track.mask_statuses[index] not in {"accepted", "repaired"}:
            continue
        prev_index = previous_present_index(track, index)
        next_index = next_present_index(track, index)
        if prev_index is None or next_index is None:
            continue
        prev_box = track.boxes[prev_index]
        next_box = track.boxes[next_index]
        if prev_box is None or next_box is None:
            continue
        predicted = np.array(
            [(prev_box.center_x + next_box.center_x) * 0.5, (prev_box.center_y + next_box.center_y) * 0.5]
        )
        actual = np.array([box.center_x, box.center_y])
        diag = float(np.hypot(sequence.base_alpha_frames[index].shape[1], sequence.base_alpha_frames[index].shape[0]))
        if float(np.linalg.norm(actual - predicted)) > limit * diag:
            track.masks[index] = np.zeros_like(track.masks[index], dtype=bool)
            track.boxes[index] = None
            track.mask_statuses[index] = "rejected_jump"
            track.warnings.append(f"frame {index} rejected: trajectory outlier")


def previous_present_index(track: PartTrack, index: int) -> int | None:
    count = len(track.masks)
    for offset in range(1, count):
        candidate = (index - offset) % count
        if np.any(track.masks[candidate]):
            return candidate
    return None


def next_present_index(track: PartTrack, index: int) -> int | None:
    count = len(track.masks)
    for offset in range(1, count):
        candidate = (index + offset) % count
        if np.any(track.masks[candidate]):
            return candidate
    return None


def update_track_presence_and_metrics(track: PartTrack, metrics: list[dict[str, object]] | None = None) -> None:
    track.presence = [bool(np.any(mask)) for mask in track.masks]
    if not track.mask_statuses or len(track.mask_statuses) != len(track.masks):
        track.mask_statuses = ["accepted" if present else "missing" for present in track.presence]
    if metrics is None or len(metrics) != len(track.masks):
        metrics = [{"frame": index} for index in range(len(track.masks))]
    for index, metric in enumerate(metrics):
        metric["status"] = track.mask_statuses[index]
        metric["area"] = int(track.masks[index].sum())
        if metric["area"] == 0:
            metric["areaRatio"] = 0.0
            metric["silhouetteRatio"] = 0.0
        prev_index = (index - 1) % len(track.masks) if track.masks else index
        metric["iouPrev"] = round4(mask_iou(track.masks[index], track.masks[prev_index])) if track.masks else 0.0
    track.frame_metrics = metrics


def reject_cross_track_conflicts(tracks: list[PartTrack]) -> None:
    for frame_index in range(max((len(track.masks) for track in tracks), default=0)):
        for left_index, left in enumerate(tracks):
            if left.id == "body" or frame_index >= len(left.masks) or not np.any(left.masks[frame_index]):
                continue
            for right in tracks[left_index + 1 :]:
                if right.id == "body" or frame_index >= len(right.masks) or not np.any(right.masks[frame_index]):
                    continue
                overlap = int(np.logical_and(left.masks[frame_index], right.masks[frame_index]).sum())
                smaller = max(1, min(int(left.masks[frame_index].sum()), int(right.masks[frame_index].sum())))
                if overlap / smaller <= 0.82:
                    continue
                loser = left if left.confidence < right.confidence else right
                loser.masks[frame_index] = np.zeros_like(loser.masks[frame_index], dtype=bool)
                loser.boxes[frame_index] = None
                ensure_status_length(loser)
                loser.mask_statuses[frame_index] = "rejected_wrong_part"
                loser.warnings.append(
                    f"frame {frame_index} rejected: overlaps {right.id if loser is left else left.id}"
                )
                update_track_presence_and_metrics(loser, loser.frame_metrics)


def ensure_status_length(track: PartTrack) -> None:
    if len(track.mask_statuses) != len(track.masks):
        track.mask_statuses = ["accepted" if np.any(mask) else "missing" for mask in track.masks]


def merge_duplicate_tracks(tracks: list[PartTrack]) -> list[PartTrack]:
    kept: list[PartTrack] = []
    for track in tracks:
        duplicate = False
        for other in kept:
            if mean_iou(track.masks, other.masks) > 0.82:
                other.confidence = max(other.confidence, track.confidence)
                other.warnings.append(f"merged duplicate part {track.id}")
                duplicate = True
                break
        if not duplicate:
            kept.append(track)
    return kept


def mean_iou(left: list[np.ndarray], right: list[np.ndarray]) -> float:
    values: list[float] = []
    for a, b in zip(left, right):
        value = mask_iou(a, b)
        if value > 0:
            values.append(value)
    return float(np.mean(values)) if values else 0.0


def stabilize_parts(
    sequence: FrameSequence,
    tracks: list[PartTrack],
    options: dict[str, object] | None = None,
) -> tuple[list[np.ndarray], list[PartTrack], SemanticMetrics]:
    options = options or {}
    frames = [frame.copy() for frame in sequence.final_rgba_frames]
    for track in tracks:
        ensure_status_length(track)
        if part_setting_bool(track, options, "enabled", "partStabilizeEnabled", True):
            if part_setting_bool(track, options, "repairEnabled", "partRepairEnabled", True):
                repair_missing_part_masks(track, sequence, options)
            if track.mobility in {"static", "low", "accessory"}:
                apply_reference_patch_lock(frames, track, sequence, options)
                apply_local_temporal_median(frames, track, sequence, options)
        flag_track_quality(track)
    metrics = compute_semantic_metrics(tracks)
    return frames, tracks, metrics


def part_setting_float(
    track: PartTrack, options: dict[str, object], part_key: str, global_key: str, default: float
) -> float:
    raw = track.stabilize_settings.get(part_key, options.get(global_key, default))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def part_setting_bool(
    track: PartTrack, options: dict[str, object], part_key: str, global_key: str, default: bool
) -> bool:
    raw = track.stabilize_settings.get(part_key, options.get(global_key, default))
    return bool(raw)


def repair_missing_part_masks(track: PartTrack, sequence: FrameSequence, options: dict[str, object]) -> None:
    if track.persistence != "always":
        return
    for index, status in enumerate(list(track.mask_statuses)):
        if np.any(track.masks[index]) and status in {"accepted", "repaired"}:
            continue
        source_index = nearest_repair_source(track, index)
        if source_index is None:
            track.warnings.append(f"missing frame {index}: manual review required")
            continue
        repaired = repair_mask_from_source(track, sequence, source_index, index, options)
        if not np.any(repaired):
            track.warnings.append(f"missing frame {index}: repair failed; manual review required")
            continue
        track.masks[index] = repaired
        track.boxes[index] = box_from_mask(index, repaired)
        track.mask_statuses[index] = "repaired"
        track.warnings.append(f"frame {index} repaired from frame {source_index}")
    update_track_presence_and_metrics(track, track.frame_metrics)


def repair_single_frame_gaps(track: PartTrack) -> None:
    ensure_status_length(track)
    for index in range(1, len(track.masks) - 1):
        if np.any(track.masks[index]) or not np.any(track.masks[index - 1]) or not np.any(track.masks[index + 1]):
            continue
        current_shape = track.masks[index].shape
        previous = resize_mask(track.masks[index - 1], current_shape)
        following = resize_mask(track.masks[index + 1], current_shape)
        repaired = np.logical_or(previous, following)
        track.masks[index] = repaired
        track.boxes[index] = box_from_mask(index, repaired)
        track.mask_statuses[index] = "repaired"
        track.warnings.append(f"missing frame {index} repaired from adjacent frames")
    update_track_presence_and_metrics(track, track.frame_metrics)


def nearest_repair_source(track: PartTrack, index: int) -> int | None:
    count = len(track.masks)
    candidates = [
        candidate
        for candidate, mask in enumerate(track.masks)
        if candidate != index and np.any(mask) and track.mask_statuses[candidate] in {"accepted", "repaired"}
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: min(abs(candidate - index), count - abs(candidate - index)))


def repair_mask_from_source(
    track: PartTrack,
    sequence: FrameSequence,
    source_index: int,
    target_index: int,
    options: dict[str, object],
) -> np.ndarray:
    source_mask = track.masks[source_index]
    source_box = track.boxes[source_index] or box_from_mask(source_index, source_mask)
    target_shape = sequence.base_alpha_frames[target_index].shape
    if source_box is None:
        return np.zeros(target_shape, dtype=bool)

    source_gray = frame_gray(sequence.final_rgba_frames[source_index])
    target_gray = frame_gray(sequence.final_rgba_frames[target_index])
    pad = 2
    x0 = max(0, int(source_box.x) - pad)
    y0 = max(0, int(source_box.y) - pad)
    x1 = min(source_gray.shape[1], int(source_box.x + source_box.width) + pad)
    y1 = min(source_gray.shape[0], int(source_box.y + source_box.height) + pad)
    template = source_gray[y0:y1, x0:x1]
    if template.shape[0] < 3 or template.shape[1] < 3:
        translated = shift_mask_to_shape(source_mask, target_shape, 0, 0)
        return clean_repaired_mask(translated, sequence, target_index)

    radius = repair_search_radius(
        source_box,
        track.mobility,
        part_setting_float(track, options, "repairSearchScale", "partRepairSearchScale", 1.0),
    )
    sx0 = max(0, x0 - radius)
    sy0 = max(0, y0 - radius)
    sx1 = min(target_gray.shape[1], x1 + radius)
    sy1 = min(target_gray.shape[0], y1 + radius)
    search = target_gray[sy0:sy1, sx0:sx1]
    if search.shape[0] < template.shape[0] or search.shape[1] < template.shape[1]:
        translated = shift_mask_to_shape(source_mask, target_shape, 0, 0)
        return clean_repaired_mask(translated, sequence, target_index)

    result = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
    _min_value, max_value, _min_loc, max_loc = cv2.minMaxLoc(result)
    if max_value < 0.15:
        track.warnings.append(f"frame {target_index}: weak repair match {max_value:.2f}")
        translated = shift_mask_to_shape(source_mask, target_shape, 0, 0)
        return clean_repaired_mask(translated, sequence, target_index)
    best_x = sx0 + int(max_loc[0])
    best_y = sy0 + int(max_loc[1])
    translated = shift_mask_to_shape(source_mask, target_shape, best_x - x0, best_y - y0)
    repaired = clean_repaired_mask(translated, sequence, target_index)
    if int(repaired.sum()) < int(source_mask.sum()) * 0.35:
        fallback = clean_repaired_mask(shift_mask_to_shape(source_mask, target_shape, 0, 0), sequence, target_index)
        if int(fallback.sum()) > int(repaired.sum()):
            track.warnings.append(f"frame {target_index}: repair fallback kept source position")
            return fallback
    return repaired


def frame_gray(frame: np.ndarray) -> np.ndarray:
    if frame.shape[2] == 4:
        rgba = frame.astype(np.float32)
        alpha = rgba[:, :, 3:4] / 255.0
        rgb = rgba[:, :, :3] * alpha + 128.0 * (1.0 - alpha)
    else:
        rgb = frame.astype(np.float32)
    return cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)


def repair_search_radius(box: object, mobility: str, scale_override: float = 1.0) -> int:
    scale = {
        "static": 0.35,
        "low": 0.55,
        "medium": 0.80,
        "high": 1.10,
        "accessory": 0.90,
    }.get(mobility, 0.80)
    scale *= max(0.1, min(3.0, scale_override))
    return max(6, int(max(float(box.width), float(box.height)) * scale))


def shift_mask_to_shape(mask: np.ndarray, shape: tuple[int, int], dx: int, dy: int) -> np.ndarray:
    target = np.zeros(shape, dtype=bool)
    src_h, src_w = mask.shape
    dst_h, dst_w = shape
    src_x0 = max(0, -dx)
    src_y0 = max(0, -dy)
    dst_x0 = max(0, dx)
    dst_y0 = max(0, dy)
    width = min(src_w - src_x0, dst_w - dst_x0)
    height = min(src_h - src_y0, dst_h - dst_y0)
    if width <= 0 or height <= 0:
        return target
    target[dst_y0 : dst_y0 + height, dst_x0 : dst_x0 + width] = mask[src_y0 : src_y0 + height, src_x0 : src_x0 + width]
    return target


def clean_repaired_mask(mask: np.ndarray, sequence: FrameSequence, frame_index: int) -> np.ndarray:
    alpha_mask = dilate(sequence.base_alpha_frames[frame_index] > 10, 2)
    cleaned = mask & alpha_mask
    if not np.any(cleaned):
        return cleaned
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    cleaned_u8 = cv2.morphologyEx(bool_to_uint8(cleaned), cv2.MORPH_CLOSE, kernel)
    cleaned_u8 = cv2.morphologyEx(cleaned_u8, cv2.MORPH_OPEN, kernel)
    return (cleaned_u8 > 0) & alpha_mask


def resize_mask(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    if mask.shape == shape:
        return mask
    return cv2.resize(mask.astype(np.uint8), (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)


def apply_reference_patch_lock(
    frames: list[np.ndarray], track: PartTrack, sequence: FrameSequence, options: dict[str, object]
) -> None:
    base_strength = {"static": 0.58, "low": 0.38, "accessory": 0.42}.get(track.mobility, 0.0)
    strength = base_strength * max(
        0.0, min(1.5, part_setting_float(track, options, "patchLockStrength", "partPatchLockStrength", 1.0))
    )
    if strength <= 0 or len(frames) < 2:
        return
    reference_index = reference_frame_index(track)
    if reference_index is None:
        return
    for index, frame in enumerate(frames):
        if index == reference_index or not track_good_for_stabilize(track, index):
            continue
        if index >= len(sequence.sam_rgb_frames) or reference_index >= len(sequence.sam_rgb_frames):
            continue
        canvas_shape = (
            sequence.sam_rgb_frames[index].shape[0],
            sequence.sam_rgb_frames[index].shape[1],
            frame.shape[2],
        )
        current_canvas = frame_to_semantic_canvas(frame, canvas_shape, sequence.semantic_offsets[index]).astype(
            np.float32
        )
        reference_canvas = frame_to_semantic_canvas(
            frames[reference_index], canvas_shape, sequence.semantic_offsets[reference_index]
        ).astype(np.float32)
        current_mask = mask_to_semantic_canvas(track.masks[index], canvas_shape[:2], sequence.semantic_offsets[index])
        reference_mask = mask_to_semantic_canvas(
            track.masks[reference_index], canvas_shape[:2], sequence.semantic_offsets[reference_index]
        )
        if not np.any(current_mask) or not np.any(reference_mask):
            continue
        current_center = mask_center(current_mask)
        reference_center = mask_center(reference_mask)
        dx = float(current_center[0] - reference_center[0])
        dy = float(current_center[1] - reference_center[1])
        matrix = np.float32([[1, 0, dx], [0, 1, dy]])
        shifted_reference = cv2.warpAffine(
            reference_canvas,
            matrix,
            (canvas_shape[1], canvas_shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        shifted_mask = (
            cv2.warpAffine(
                bool_to_uint8(reference_mask),
                matrix,
                (canvas_shape[1], canvas_shape[0]),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            > 0
        )
        overlap = mask_iou(current_mask, shifted_mask)
        if overlap < patch_lock_min_iou(track.mobility):
            track.warnings.append(f"frame {index}: patch lock skipped, ref IoU {overlap:.2f}")
            continue
        blend_mask = current_mask & shifted_mask
        if not np.any(blend_mask):
            continue
        soft = cv2.GaussianBlur(bool_to_uint8(blend_mask), (5, 5), 0).astype(np.float32)[:, :, None] / 255.0
        blended = current_canvas * (1.0 - soft * strength) + shifted_reference * (soft * strength)
        frames[index] = semantic_canvas_to_frame(blended, frame.shape, sequence.semantic_offsets[index])


def reference_frame_index(track: PartTrack) -> int | None:
    candidates = [
        (index, int(mask.sum())) for index, mask in enumerate(track.masks) if track_good_for_stabilize(track, index)
    ]
    if not candidates:
        return None
    areas = np.array([area for _index, area in candidates], dtype=np.float32)
    median_area = float(np.median(areas))
    return min(candidates, key=lambda item: abs(float(item[1]) - median_area))[0]


def track_good_for_stabilize(track: PartTrack, index: int) -> bool:
    if index >= len(track.masks) or not np.any(track.masks[index]):
        return False
    ensure_status_length(track)
    return track.mask_statuses[index] in {"accepted", "repaired"}


def mask_center(mask: np.ndarray) -> tuple[float, float]:
    ys, xs = np.where(mask)
    if xs.size == 0:
        return 0.0, 0.0
    return float(xs.mean()), float(ys.mean())


def patch_lock_min_iou(mobility: str) -> float:
    return {
        "static": 0.12,
        "low": 0.08,
        "accessory": 0.05,
    }.get(mobility, 0.10)


def apply_local_temporal_median(
    frames: list[np.ndarray], track: PartTrack, sequence: FrameSequence, options: dict[str, object]
) -> None:
    base_strength = {"static": 0.55, "low": 0.35, "accessory": 0.45}.get(track.mobility, 0.0)
    strength = base_strength * max(
        0.0, min(1.5, part_setting_float(track, options, "medianStrength", "partMedianStrength", 1.0))
    )
    if strength <= 0 or len(frames) < 3:
        return
    for index in range(1, len(frames) - 1):
        mask = track.masks[index]
        if not np.any(mask) or not track_good_for_stabilize(track, index):
            continue
        if index >= len(sequence.sam_rgb_frames) or index >= len(sequence.semantic_offsets):
            continue
        canvas_shape = (
            sequence.sam_rgb_frames[index].shape[0],
            sequence.sam_rgb_frames[index].shape[1],
            frames[index].shape[2],
        )
        stack = np.stack(
            [
                frame_to_semantic_canvas(frames[index - 1], canvas_shape, sequence.semantic_offsets[index - 1]),
                frame_to_semantic_canvas(frames[index], canvas_shape, sequence.semantic_offsets[index]),
                frame_to_semantic_canvas(frames[index + 1], canvas_shape, sequence.semantic_offsets[index + 1]),
            ],
            axis=0,
        ).astype(np.float32)
        median = np.median(stack, axis=0)
        current_canvas = stack[1]
        canvas_mask = mask_to_semantic_canvas(mask, canvas_shape[:2], sequence.semantic_offsets[index])
        soft = cv2.GaussianBlur(bool_to_uint8(canvas_mask), (3, 3), 0).astype(np.float32)[:, :, None] / 255.0
        blended_canvas = current_canvas * (1.0 - soft * strength) + median * (soft * strength)
        frames[index] = semantic_canvas_to_frame(blended_canvas, frames[index].shape, sequence.semantic_offsets[index])


def frame_to_semantic_canvas(
    frame: np.ndarray, canvas_shape: tuple[int, int, int], offset: tuple[int, int]
) -> np.ndarray:
    canvas = np.zeros(canvas_shape, dtype=frame.dtype)
    offset_x, offset_y = offset
    x0 = max(0, offset_x)
    y0 = max(0, offset_y)
    x1 = min(canvas_shape[1], offset_x + frame.shape[1])
    y1 = min(canvas_shape[0], offset_y + frame.shape[0])
    if x1 <= x0 or y1 <= y0:
        return canvas
    src_x0 = x0 - offset_x
    src_y0 = y0 - offset_y
    canvas[y0:y1, x0:x1, :] = frame[src_y0 : src_y0 + (y1 - y0), src_x0 : src_x0 + (x1 - x0), :]
    return canvas


def mask_to_semantic_canvas(mask: np.ndarray, canvas_shape: tuple[int, int], offset: tuple[int, int]) -> np.ndarray:
    canvas = np.zeros(canvas_shape, dtype=bool)
    offset_x, offset_y = offset
    x0 = max(0, offset_x)
    y0 = max(0, offset_y)
    x1 = min(canvas_shape[1], offset_x + mask.shape[1])
    y1 = min(canvas_shape[0], offset_y + mask.shape[0])
    if x1 <= x0 or y1 <= y0:
        return canvas
    src_x0 = x0 - offset_x
    src_y0 = y0 - offset_y
    canvas[y0:y1, x0:x1] = mask[src_y0 : src_y0 + (y1 - y0), src_x0 : src_x0 + (x1 - x0)]
    return canvas


def semantic_canvas_to_frame(
    canvas: np.ndarray, frame_shape: tuple[int, int, int], offset: tuple[int, int]
) -> np.ndarray:
    frame = np.zeros(frame_shape, dtype=np.uint8)
    offset_x, offset_y = offset
    x0 = max(0, offset_x)
    y0 = max(0, offset_y)
    x1 = min(canvas.shape[1], offset_x + frame_shape[1])
    y1 = min(canvas.shape[0], offset_y + frame_shape[0])
    if x1 <= x0 or y1 <= y0:
        return frame
    dst_x0 = x0 - offset_x
    dst_y0 = y0 - offset_y
    frame[dst_y0 : dst_y0 + (y1 - y0), dst_x0 : dst_x0 + (x1 - x0), :] = np.clip(
        canvas[y0:y1, x0:x1, :], 0, 255
    ).astype(np.uint8)
    return frame


def flag_track_quality(track: PartTrack) -> None:
    missing = [index for index, present in enumerate(track.presence) if track.persistence == "always" and not present]
    if missing:
        track.warnings.append(f"missing always-present frames {missing}: manual review required")

    areas = np.array([float(mask.sum()) for mask in track.masks], dtype=np.float32)
    visible = areas[areas > 0]
    if visible.size < 2 or float(visible.mean()) <= 0:
        return
    area_jitter = float(visible.std() / visible.mean())
    threshold = {"static": 0.45, "low": 0.65, "accessory": 0.85}.get(track.mobility)
    if threshold is not None and area_jitter > threshold:
        track.warnings.append(f"unstable area jitter {area_jitter:.2f}: manual review required")

    previous = None
    for index, area in enumerate(areas):
        if area <= 0:
            continue
        if previous is not None:
            ratio = max(area, previous) / max(1.0, min(area, previous))
            jump_threshold = 3.0 if track.mobility == "accessory" else 2.2
            if ratio > jump_threshold:
                track.warnings.append(f"frame {index}: abrupt area change {ratio:.2f}x")
        previous = area
