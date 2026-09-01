from __future__ import annotations


import cv2
import numpy as np

from asset_pipeline.services.image_ops import bool_to_uint8


def option_float(options: dict[str, object], key: str, default: float) -> float:
    value = options.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def option_int(options: dict[str, object], key: str, default: int) -> int:
    value = options.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clean_alpha_islands(rgba: np.ndarray, options: dict[str, object]) -> np.ndarray:
    min_area = max(0, option_int(options, "alphaCleanupMinArea", 24))
    close_size = max(0, option_int(options, "alphaCleanupCloseSize", 0))
    alpha_cutoff = max(0, min(255, option_int(options, "alphaCutoff", 10)))
    if min_area <= 0 and close_size <= 1:
        return rgba

    alpha = rgba[:, :, 3]
    visible = alpha > alpha_cutoff
    if close_size > 1:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_size, close_size))
        visible = cv2.morphologyEx(bool_to_uint8(visible), cv2.MORPH_CLOSE, kernel) > 0

    if min_area > 0:
        component_count, labels, stats, _centroids = cv2.connectedComponentsWithStats(bool_to_uint8(visible), 8)
        keep = np.zeros_like(visible, dtype=bool)
        for component_index in range(1, component_count):
            area = int(stats[component_index, cv2.CC_STAT_AREA])
            if area >= min_area:
                keep |= labels == component_index
        visible = keep

    cleaned = rgba.copy()
    cleaned[:, :, 3] = np.where(visible, alpha, 0).astype(np.uint8)
    return cleaned


def split_sheet(sheet: np.ndarray, frame_count: int, frame_width: int) -> np.ndarray:
    height = sheet.shape[0]
    return sheet.reshape(height, frame_count, frame_width, 4).transpose(1, 0, 2, 3)


def join_sheet(frames: np.ndarray) -> np.ndarray:
    frame_count, height, frame_width, channels = frames.shape
    return frames.transpose(1, 0, 2, 3).reshape(height, frame_count * frame_width, channels)


def rgba_to_flow_gray(frame: np.ndarray) -> np.ndarray:
    rgba = frame.astype(np.float32)
    alpha = rgba[:, :, 3:4] / 255.0
    composed = rgba[:, :, :3] * alpha + 128.0 * (1.0 - alpha)
    return cv2.cvtColor(np.clip(composed, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)


def remap_with_flow(
    image: np.ndarray, flow: np.ndarray, interpolation: int = cv2.INTER_LINEAR
) -> tuple[np.ndarray, np.ndarray]:
    height, width = flow.shape[:2]
    grid_x, grid_y = np.meshgrid(np.arange(width, dtype=np.float32), np.arange(height, dtype=np.float32))
    map_x = grid_x + flow[:, :, 0]
    map_y = grid_y + flow[:, :, 1]
    valid = (map_x >= 0.0) & (map_x <= width - 1) & (map_y >= 0.0) & (map_y <= height - 1)
    warped = cv2.remap(
        image,
        map_x.astype(np.float32),
        map_y.astype(np.float32),
        interpolation,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return warped, valid


def flow_guided_deflicker_sheet(
    sheet: np.ndarray,
    frame_count: int,
    frame_width: int,
    options: dict[str, object],
) -> tuple[np.ndarray, dict[str, float | int]]:
    strength = np.clip(option_float(options, "flowDeflickerStrength", 0.55), 0.0, 1.0)
    radius = max(0, min(3, option_int(options, "flowDeflickerRadius", 1)))
    if frame_count < 2 or frame_width <= 0 or strength <= 0.0 or radius <= 0:
        return sheet, {"blendedPixelRatio": 0.0, "blendedPixelCount": 0, "pairCount": 0}

    color_tolerance = max(1.0, option_float(options, "flowColorTolerance", 34.0))
    alpha_tolerance = max(1.0, option_float(options, "flowAlphaTolerance", 58.0))
    consistency_tolerance = max(0.25, option_float(options, "flowConsistencyTolerance", 2.8))
    max_displacement = max(1.0, option_float(options, "flowMaxDisplacement", 42.0))
    confidence_floor = np.clip(option_float(options, "flowConfidenceFloor", 0.4), 0.0, 1.0)
    alpha_cutoff = max(0, min(255, option_int(options, "alphaCutoff", 10)))

    source = split_sheet(sheet, frame_count, frame_width)
    source_float = source.astype(np.float32)
    grays = [rgba_to_flow_gray(frame) for frame in source]
    result = source_float.copy()
    blended_pixels = 0
    pair_count = 0

    for index in range(frame_count):
        target = source_float[index]
        accum = target.copy()
        weights = np.ones(target.shape[:2], dtype=np.float32)
        accepted_any = np.zeros(target.shape[:2], dtype=bool)

        for offset in range(-radius, radius + 1):
            if offset == 0:
                continue
            neighbor_index = index + offset
            if neighbor_index < 0 or neighbor_index >= frame_count:
                continue

            flow_to_neighbor = cv2.calcOpticalFlowFarneback(
                grays[index],
                grays[neighbor_index],
                None,
                0.5,
                4,
                21,
                4,
                7,
                1.5,
                cv2.OPTFLOW_FARNEBACK_GAUSSIAN,
            )
            flow_to_target = cv2.calcOpticalFlowFarneback(
                grays[neighbor_index],
                grays[index],
                None,
                0.5,
                4,
                21,
                4,
                7,
                1.5,
                cv2.OPTFLOW_FARNEBACK_GAUSSIAN,
            )
            warped_neighbor, valid = remap_with_flow(source_float[neighbor_index], flow_to_neighbor)
            warped_reverse_flow, _valid_flow = remap_with_flow(flow_to_target, flow_to_neighbor)

            flow_magnitude = np.sqrt(np.sum(flow_to_neighbor * flow_to_neighbor, axis=2))
            consistency = np.sqrt(np.sum((flow_to_neighbor + warped_reverse_flow) ** 2, axis=2))
            color_diff = np.mean(np.abs(target[:, :, :3] - warped_neighbor[:, :, :3]), axis=2)
            alpha_diff = np.abs(target[:, :, 3] - warped_neighbor[:, :, 3])
            visible = (target[:, :, 3] > alpha_cutoff) & (warped_neighbor[:, :, 3] > alpha_cutoff)
            accepted = (
                valid
                & visible
                & (flow_magnitude <= max_displacement)
                & (consistency <= consistency_tolerance)
                & (color_diff <= color_tolerance)
                & (alpha_diff <= alpha_tolerance)
            )
            if not np.any(accepted):
                continue

            confidence = (
                (1.0 - np.clip(color_diff / color_tolerance, 0.0, 1.0))
                * (1.0 - np.clip(alpha_diff / alpha_tolerance, 0.0, 1.0))
                * (1.0 - np.clip(consistency / consistency_tolerance, 0.0, 1.0))
            )
            confidence = np.where(accepted, confidence_floor + (1.0 - confidence_floor) * confidence, 0.0)
            temporal_weight = 1.0 / float(abs(offset))
            weight = np.where(accepted, strength * temporal_weight * confidence, 0.0).astype(np.float32)
            accum += warped_neighbor * weight[:, :, None]
            weights += weight
            accepted_any |= accepted
            pair_count += 1

        result[index] = accum / weights[:, :, None]
        blended_pixels += int(accepted_any.sum())

    blended_ratio = float(blended_pixels / max(1, frame_count * source.shape[1] * source.shape[2]))
    return join_sheet(np.clip(result, 0, 255).astype(np.uint8)), {
        "blendedPixelRatio": round(blended_ratio, 4),
        "blendedPixelCount": int(blended_pixels),
        "pairCount": int(pair_count),
    }


def temporal_deflicker_sheet(
    sheet: np.ndarray,
    frame_count: int,
    frame_width: int,
    options: dict[str, object],
) -> tuple[np.ndarray, dict[str, float | int]]:
    strength = np.clip(option_float(options, "temporalDeflickerStrength", 0.45), 0.0, 1.0)
    if frame_count < 3 or frame_width <= 0 or strength <= 0.0:
        return sheet, {"stablePixelRatio": 0.0, "stablePixelCount": 0}

    coverage = np.clip(option_float(options, "temporalStaticCoverage", 0.68), 0.0, 1.0)
    color_tolerance = max(0.0, option_float(options, "temporalColorTolerance", 18.0))
    alpha_tolerance = max(0.0, option_float(options, "temporalAlphaTolerance", 38.0))
    alpha_cutoff = max(0, min(255, option_int(options, "alphaCutoff", 10)))

    frames = split_sheet(sheet, frame_count, frame_width).astype(np.float32)
    rgb = frames[:, :, :, :3]
    alpha = frames[:, :, :, 3]
    visible = alpha > alpha_cutoff
    visible_ratio = visible.mean(axis=0)

    median_rgb = np.median(rgb, axis=0)
    median_alpha = np.median(alpha, axis=0)
    color_mad = np.median(np.abs(rgb - median_rgb), axis=0).mean(axis=2)
    alpha_mad = np.median(np.abs(alpha - median_alpha), axis=0)
    stable = (visible_ratio >= coverage) & (color_mad <= color_tolerance) & (alpha_mad <= alpha_tolerance)
    if not np.any(stable):
        return sheet, {"stablePixelRatio": 0.0, "stablePixelCount": 0}

    frames[:, stable, :3] = frames[:, stable, :3] * (1.0 - strength) + median_rgb[stable] * strength
    frames[:, stable, 3] = frames[:, stable, 3] * (1.0 - strength) + median_alpha[stable] * strength
    result = np.clip(frames, 0, 255).astype(np.uint8)
    stable_count = int(stable.sum())
    stable_ratio = float(stable.mean())
    return join_sheet(result), {"stablePixelRatio": round(stable_ratio, 4), "stablePixelCount": stable_count}


def extrude_frame_edges(frame: np.ndarray, pixels: int, alpha_cutoff: int) -> np.ndarray:
    if pixels <= 0:
        return frame
    result = frame.copy()
    alpha = result[:, :, 3]
    visible = alpha > alpha_cutoff
    if not np.any(visible):
        return result

    filled = visible.copy()
    rgb = result[:, :, :3]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    for _ in range(pixels):
        border = (cv2.dilate(bool_to_uint8(filled), kernel) > 0) & ~filled
        if not np.any(border):
            break
        distance, labels = cv2.distanceTransformWithLabels(
            bool_to_uint8(~filled),
            cv2.DIST_L2,
            3,
            labelType=cv2.DIST_LABEL_PIXEL,
        )
        _ = distance
        ys, xs = np.where(filled)
        if ys.size == 0:
            break
        label_to_pixel = np.column_stack([ys, xs])
        nearest = label_to_pixel[np.maximum(labels[border] - 1, 0)]
        rgb[border] = rgb[nearest[:, 0], nearest[:, 1]]
        filled[border] = True
    result[:, :, :3] = rgb
    result[:, :, 3] = alpha
    return result


def extrude_sheet_edges(
    sheet: np.ndarray,
    frame_count: int,
    frame_width: int,
    options: dict[str, object],
) -> tuple[np.ndarray, dict[str, int]]:
    pixels = max(0, option_int(options, "sheetExtrudePixels", 2))
    if frame_count <= 0 or frame_width <= 0 or pixels <= 0:
        return sheet, {"pixels": 0}
    alpha_cutoff = max(0, min(255, option_int(options, "alphaCutoff", 10)))
    frames = split_sheet(sheet, frame_count, frame_width)
    extruded = np.stack([extrude_frame_edges(frame, pixels, alpha_cutoff) for frame in frames], axis=0)
    return join_sheet(extruded), {"pixels": pixels}
