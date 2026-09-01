from __future__ import annotations

import os
import re
from dataclasses import asdict

import numpy as np
import cv2

from asset_pipeline.services.image_ops import round4
from asset_pipeline.services.mask_codec import encode_rle_mask
from asset_pipeline.services.semantic_client import qwen_base_url
from asset_pipeline.services.semantic_models import PartTrack, SemanticMetrics


def mask_iou(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        right = cv2.resize(
            right.astype(np.uint8), (left.shape[1], left.shape[0]), interpolation=cv2.INTER_NEAREST
        ).astype(bool)
    union = np.logical_or(left, right).sum()
    if union == 0:
        return 0.0
    return float(np.logical_and(left, right).sum()) / float(union)


def compute_semantic_metrics(tracks: list[PartTrack]) -> SemanticMetrics:
    if not tracks:
        return SemanticMetrics()
    presence_failures = sum(
        1 for track in tracks if track.persistence == "always" for present in track.presence if not present
    )
    confidences = [track.confidence for track in tracks]
    area_jitters: list[float] = []
    centroid_jitters: list[float] = []
    for track in tracks:
        areas = np.array([float(mask.sum()) for mask in track.masks if np.any(mask)], dtype=np.float32)
        centers = np.array(
            [(box.center_x, box.center_y) for box in track.boxes if box is not None],
            dtype=np.float32,
        )
        if areas.size > 1 and float(areas.mean()) > 0:
            area_jitters.append(float(areas.std() / areas.mean()))
        if len(centers) > 1:
            centroid_jitters.append(float(np.linalg.norm(np.diff(centers, axis=0), axis=1).mean()))
    manual_review = presence_failures > 0 or any(
        "manual review" in warning for track in tracks for warning in track.warnings
    )
    return SemanticMetrics(
        part_presence_failures=int(presence_failures),
        part_area_jitter=round4(float(np.mean(area_jitters)) if area_jitters else 0.0),
        part_centroid_jitter=round4(float(np.mean(centroid_jitters)) if centroid_jitters else 0.0),
        part_edge_jitter=0.0,
        semantic_confidence_min=round4(float(min(confidences)) if confidences else 0.0),
        manual_review_required=manual_review,
    )


def semantic_metadata(
    tracks: list[PartTrack], metrics: SemanticMetrics, warnings: list[str], mask_model: str = "sam3"
) -> dict[str, object]:
    disabled = any(warning in {"semantic disabled", "semantic stages disabled"} for warning in warnings)
    issues = semantic_issues(tracks, warnings)
    return {
        "enabled": bool(tracks) or not disabled,
        "sam3Url": os.environ.get("ASSET_PIPELINE_SAM3_URL", "http://localhost:8765"),
        "maskModel": mask_model,
        "vlmBaseUrl": qwen_base_url(),
        "warnings": warnings,
        "semanticIssues": issues,
        "parts": [
            {
                "id": track.id,
                "label": track.label,
                "color": "#%02X%02X%02X" % track.color,
                "mobility": track.mobility,
                "persistence": track.persistence,
                "confidence": round4(track.confidence),
                "presence": track.presence,
                "warnings": track.warnings,
                "boxes": [asdict(box) if box else None for box in track.boxes],
                "masks": [encode_rle_mask(mask) for mask in track.masks],
                "maskStatuses": normalized_statuses(track),
                "frameMetrics": track.frame_metrics,
                "trackSummary": track_summary(track),
                "stabilizeSettings": dict(track.stabilize_settings),
            }
            for track in tracks
        ],
        "metrics": asdict(metrics),
    }


def semantic_issues(tracks: list[PartTrack], warnings: list[str]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    seen: set[tuple[str | None, int | None, str, str]] = set()

    def add(part_id: str | None, frame: int | None, issue_type: str, severity: str, message: str, source: str) -> None:
        key = (part_id, frame, issue_type, message)
        if key in seen:
            return
        seen.add(key)
        item: dict[str, object] = {
            "type": issue_type,
            "severity": severity,
            "source": source,
            "message": message,
        }
        if part_id is not None:
            item["partId"] = part_id
        if frame is not None:
            item["frame"] = frame
        issues.append(item)

    for warning in warnings:
        add(None, None, classify_warning(warning), "info", warning, "backend_validation")

    for track in tracks:
        for index, present in enumerate(track.presence):
            if track.persistence == "always" and not present:
                add(
                    track.id,
                    index,
                    "missing_always_present",
                    "review",
                    f"{track.label} missing on frame {index}",
                    "backend_validation",
                )
        for warning in track.warnings:
            frame = warning_frame(warning)
            issue_type = classify_warning(warning)
            severity = (
                "review"
                if "manual review" in warning
                or issue_type in {"missing_always_present", "mask_rejected", "mask_repaired"}
                else "warn"
            )
            add(track.id, frame, issue_type, severity, warning, "backend_validation")
        for index, status in enumerate(normalized_statuses(track)):
            if status in {"rejected_jump", "rejected_wrong_part", "missing"}:
                add(track.id, index, status, "review", f"{track.label} frame {index}: {status}", "track_validation")
            elif status == "repaired":
                add(track.id, index, status, "warn", f"{track.label} frame {index}: repaired", "track_repair")
    return issues


def warning_frame(warning: str) -> int | None:
    match = re.search(r"\bframe\s+(\d+)\b", warning)
    return int(match.group(1)) if match else None


def classify_warning(warning: str) -> str:
    lowered = warning.lower()
    if "repaired" in lowered:
        return "mask_repaired"
    if "trajectory outlier" in lowered or "centroid jump" in lowered or "area ratio" in lowered:
        return "rejected_jump"
    if "overlaps" in lowered or "wrong" in lowered:
        return "rejected_wrong_part"
    if "missing always-present" in lowered or "missing frame" in lowered:
        return "missing_always_present"
    if "covers >85% silhouette" in lowered or "rejected" in lowered:
        return "mask_rejected"
    if "merged duplicate" in lowered:
        return "duplicate_part"
    if "area jitter" in lowered or "abrupt area change" in lowered:
        return "jitter"
    if "grounding" in lowered:
        return "grounding"
    if "unavailable" in lowered or "disabled" in lowered or "skipped" in lowered:
        return "runtime"
    return "warning"


def normalized_statuses(track: PartTrack) -> list[str]:
    if len(track.mask_statuses) == len(track.masks):
        return list(track.mask_statuses)
    return ["accepted" if np.any(mask) else "missing" for mask in track.masks]


def track_summary(track: PartTrack) -> dict[str, object]:
    statuses = normalized_statuses(track)
    return {
        "accepted": statuses.count("accepted"),
        "repaired": statuses.count("repaired"),
        "missing": statuses.count("missing"),
        "rejected": sum(1 for status in statuses if status.startswith("rejected")),
        "areaJitter": part_area_jitter(track),
        "centroidJitter": part_centroid_jitter(track),
        "loopIoU": round4(mask_iou(track.masks[-1], track.masks[0])) if len(track.masks) > 1 else 0.0,
    }


def part_area_jitter(track: PartTrack) -> float:
    areas = np.array([float(mask.sum()) for mask in track.masks if np.any(mask)], dtype=np.float32)
    if areas.size < 2 or float(areas.mean()) <= 0:
        return 0.0
    return round4(float(areas.std() / areas.mean()))


def part_centroid_jitter(track: PartTrack) -> float:
    centers = np.array(
        [(box.center_x, box.center_y) for box in track.boxes if box is not None],
        dtype=np.float32,
    )
    if len(centers) < 2:
        return 0.0
    return round4(float(np.linalg.norm(np.diff(centers, axis=0), axis=1).mean()))
