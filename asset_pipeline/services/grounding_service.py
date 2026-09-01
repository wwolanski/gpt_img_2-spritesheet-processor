from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np

from asset_pipeline.services.semantic_models import FrameSequence, SemanticPartSpec


ProjectionMode = Literal["by_persistence", "source_only", "all_frames"]


@dataclass(frozen=True)
class GroundingSettings:
    min_confidence: float
    alpha_cutoff: int
    dilation_radius: int
    allow_frame_reassign: bool
    frame_min_score: float
    projection_mode: ProjectionMode
    expand_ratio: float
    expand_min_px: float
    emit_bbox: bool
    emit_positive_point: bool


@dataclass
class GroundingStageResult:
    edits: list[dict[str, object]]
    settings: GroundingSettings
    warnings: list[str]
    audit: dict[str, object]


def grounding_settings_from_options(options: dict[str, object]) -> GroundingSettings:
    projection_mode = str(options.get("semanticGroundingProjectionMode", "by_persistence"))
    if projection_mode not in {"by_persistence", "source_only", "all_frames"}:
        projection_mode = "by_persistence"
    return GroundingSettings(
        min_confidence=clamp_float(options.get("semanticGroundingMinConfidence", 0.35), 0.0, 1.0),
        alpha_cutoff=clamp_int(options.get("semanticGroundingAlphaCutoff", 10), 0, 255),
        dilation_radius=clamp_int(options.get("semanticGroundingDilationRadius", 2), 0, 12),
        allow_frame_reassign=option_bool(options.get("semanticGroundingAllowFrameReassign", True)),
        frame_min_score=clamp_float(options.get("semanticGroundingFrameMinScore", 0.08), 0.0, 1.0),
        projection_mode=projection_mode,  # type: ignore[arg-type]
        expand_ratio=clamp_float(options.get("semanticGroundingExpandRatio", 0.08), 0.0, 1.0),
        expand_min_px=clamp_float(options.get("semanticGroundingExpandMinPx", 2.0), 0.0, 64.0),
        emit_bbox=option_bool(options.get("semanticGroundingEmitBbox", True)),
        emit_positive_point=option_bool(options.get("semanticGroundingEmitPositivePoint", True)),
    )


def transform_grounding_hints(
    sequence: FrameSequence,
    specs: list[SemanticPartSpec],
    settings: GroundingSettings,
) -> GroundingStageResult:
    edits: list[dict[str, object]] = []
    warnings: list[str] = []
    seen: set[tuple[int, str, str, tuple[int, ...] | tuple[int, int]]] = set()
    audit = {
        "inputHints": 0,
        "acceptedHints": 0,
        "ignoredLowConfidence": 0,
        "ignoredNoForeground": 0,
        "reassignedFrames": 0,
        "projectedEdits": 0,
    }
    for spec in specs:
        for hint in spec.grounding:
            audit["inputHints"] += 1
            if hint.confidence < settings.min_confidence:
                audit["ignoredLowConfidence"] += 1
                warnings.append(
                    f"semantic grounding ignored for {spec.id}: confidence {hint.confidence:.2f} < {settings.min_confidence:.2f}"
                )
                continue
            frame_index = selected_grounding_frame(sequence, hint.frame, hint.bbox_2d, hint.point_2d, settings)
            if frame_index is None:
                audit["ignoredNoForeground"] += 1
                warnings.append(f"semantic grounding ignored for {spec.id}: no foreground overlap")
                continue
            if frame_index != hint.frame:
                audit["reassignedFrames"] += 1
                warnings.append(f"semantic grounding reassigned for {spec.id}: frame {hint.frame} -> {frame_index}")
            audit["acceptedHints"] += 1
            target_frames = projected_grounding_frames(
                sequence, spec.persistence, frame_index, settings.projection_mode
            )
            audit["projectedEdits"] += len(target_frames)
            for target_frame in target_frames:
                add_grounding_edits(edits, seen, sequence, target_frame, spec.id, hint.bbox_2d, hint.point_2d, settings)
    return GroundingStageResult(edits, settings, warnings, audit)


def selected_grounding_frame(
    sequence: FrameSequence,
    frame_index: int,
    bbox_2d: tuple[int, int, int, int],
    point_2d: tuple[int, int],
    settings: GroundingSettings,
) -> int | None:
    if 0 <= frame_index < len(sequence.sam_rgb_frames):
        current = grounding_foreground_score(sequence, frame_index, bbox_2d, point_2d, settings)
        if current >= settings.frame_min_score or not settings.allow_frame_reassign:
            return frame_index if current > 0.0 else None
    if not settings.allow_frame_reassign:
        return None
    scores = [
        (grounding_foreground_score(sequence, index, bbox_2d, point_2d, settings), index)
        for index in range(len(sequence.sam_rgb_frames))
    ]
    scores = [(score, index) for score, index in scores if score > 0.0]
    if not scores:
        return None
    best_score, best_index = max(scores, key=lambda item: item[0])
    return best_index if best_score >= settings.frame_min_score else None


def projected_grounding_frames(
    sequence: FrameSequence, persistence: str, frame_index: int, mode: ProjectionMode
) -> list[int]:
    if mode == "all_frames":
        return list(range(len(sequence.sam_rgb_frames)))
    if mode == "source_only":
        return [frame_index]
    if persistence == "always":
        return list(range(len(sequence.sam_rgb_frames)))
    return [frame_index]


def add_grounding_edits(
    edits: list[dict[str, object]],
    seen: set[tuple[int, str, str, tuple[int, ...] | tuple[int, int]]],
    sequence: FrameSequence,
    frame_index: int,
    part_id: str,
    bbox_2d: tuple[int, int, int, int],
    point_2d: tuple[int, int],
    settings: GroundingSettings,
) -> None:
    frame = sequence.sam_rgb_frames[frame_index]
    height, width = int(frame.shape[0]), int(frame.shape[1])
    x1, y1, x2, y2 = relative_box_to_pixels(bbox_2d, width, height)
    px, py = relative_point_to_pixels(point_2d, width, height)
    box = tuple(int(round(value)) for value in expand_box([x1, y1, x2, y2], width, height, settings))
    point = (int(round(px)), int(round(py)))
    box_key = (frame_index, part_id, "bbox", box)
    point_key = (frame_index, part_id, "positive_point", point)
    if settings.emit_bbox and box_key not in seen:
        edits.append({"frame": frame_index, "partId": part_id, "type": "bbox", "box": list(box)})
        seen.add(box_key)
    if settings.emit_positive_point and point_key not in seen:
        edits.append(
            {
                "frame": frame_index,
                "partId": part_id,
                "type": "positive_point",
                "x": float(point[0]),
                "y": float(point[1]),
            }
        )
        seen.add(point_key)


def grounding_foreground_score(
    sequence: FrameSequence,
    frame_index: int,
    bbox_2d: tuple[int, int, int, int],
    point_2d: tuple[int, int],
    settings: GroundingSettings,
) -> float:
    if frame_index < 0 or frame_index >= len(sequence.semantic_alpha_frames):
        return 0.0
    alpha = sequence.semantic_alpha_frames[frame_index] > settings.alpha_cutoff
    if alpha.size == 0:
        return 0.0
    alpha = dilated_bool(alpha, settings.dilation_radius)
    height, width = alpha.shape
    x1, y1, x2, y2 = [int(round(value)) for value in relative_box_to_pixels(bbox_2d, width, height)]
    x1, y1, x2, y2 = [int(round(value)) for value in expand_box([x1, y1, x2, y2], width, height, settings)]
    if x2 <= x1 or y2 <= y1:
        return 0.0
    px, py = relative_point_to_pixels(point_2d, width, height)
    point_bonus = 0.25 if alpha[int(round(py)), int(round(px))] else 0.0
    crop = alpha[y1:y2, x1:x2]
    if crop.size == 0:
        return point_bonus
    return float(crop.mean()) + point_bonus


def dilated_bool(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return mask.astype(bool)
    kernel = np.ones((radius * 2 + 1, radius * 2 + 1), dtype=np.uint8)
    import cv2

    return cv2.dilate(mask.astype(np.uint8), kernel, iterations=1).astype(bool)


def expand_box(box: list[float], width: int, height: int, settings: GroundingSettings) -> list[float]:
    x1, y1, x2, y2 = box
    pad_x = max(settings.expand_min_px, (x2 - x1) * settings.expand_ratio)
    pad_y = max(settings.expand_min_px, (y2 - y1) * settings.expand_ratio)
    return [
        max(0.0, min(float(width - 1), x1 - pad_x)),
        max(0.0, min(float(height - 1), y1 - pad_y)),
        max(1.0, min(float(width), x2 + pad_x)),
        max(1.0, min(float(height), y2 + pad_y)),
    ]


def relative_box_to_pixels(box: tuple[int, int, int, int], width: int, height: int) -> list[float]:
    x1, y1, x2, y2 = box
    return [
        max(0.0, min(float(width - 1), x1 / 1000.0 * width)),
        max(0.0, min(float(height - 1), y1 / 1000.0 * height)),
        max(1.0, min(float(width), x2 / 1000.0 * width)),
        max(1.0, min(float(height), y2 / 1000.0 * height)),
    ]


def relative_point_to_pixels(point: tuple[int, int], width: int, height: int) -> tuple[float, float]:
    x, y = point
    return (
        max(0.0, min(float(width - 1), x / 1000.0 * width)),
        max(0.0, min(float(height - 1), y / 1000.0 * height)),
    )


def grounding_result_metadata(result: GroundingStageResult | None) -> dict[str, object]:
    if result is None:
        return {"enabled": False, "edits": [], "settings": None, "warnings": [], "audit": {}}
    return {
        "enabled": True,
        "edits": result.edits,
        "settings": asdict(result.settings),
        "warnings": result.warnings,
        "audit": result.audit,
    }


def option_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def clamp_float(value: object, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(maximum, parsed))


def clamp_int(value: object, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(maximum, parsed))
