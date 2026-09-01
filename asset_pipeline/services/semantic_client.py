from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict

import numpy as np

from asset_pipeline.services.mask_codec import decode_rle_mask, encode_png_base64
from asset_pipeline.services.models import FrameBox
from asset_pipeline.services.semantic_models import FrameSequence, PartTrack, SemanticPartSpec


PALETTE = (
    (255, 176, 0),
    (116, 255, 216),
    (255, 141, 141),
    (184, 215, 255),
    (216, 255, 106),
    (210, 170, 255),
)


def semantic_enabled() -> bool:
    return os.environ.get("ASSET_PIPELINE_SEMANTIC_ENABLED", "1") == "1"


def qwen_base_url() -> str:
    return (os.environ.get("SEMANTIC_CLIENT_QWEN_BASE_URL") or "http://localhost:1234/v1").rstrip("/")


def sam3_url() -> str:
    return os.environ.get("ASSET_PIPELINE_SAM3_URL", "http://localhost:8765").rstrip("/")


def default_mask_model() -> str:
    return os.environ.get("ASSET_PIPELINE_SEMANTIC_MASK_MODEL", "sam3").strip() or "sam3"


def semantic_timeout_seconds() -> float:
    return max(1.0, int(os.environ.get("ASSET_PIPELINE_SEMANTIC_TIMEOUT_MS", "300000")) / 1000.0)


def segment_parts(
    sequence: FrameSequence,
    specs: list[SemanticPartSpec],
    warnings: list[str],
    edits: list[dict[str, object]] | None = None,
    grounding_edits: list[dict[str, object]] | None = None,
    mask_model: str | None = None,
) -> list[PartTrack]:
    if not semantic_enabled():
        warnings.append("semantic disabled")
        return []
    if not specs:
        warnings.append("semantic skipped: no part specs")
        return []

    selected_mask_model = (mask_model or default_mask_model()).strip() or "sam3"
    sam3_edits = grounding_edits if grounding_edits is not None else []
    payload = {
        "frames": [
            {
                "index": index,
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0]),
                "rgbPngBase64": encode_png_base64(frame),
            }
            for index, frame in enumerate(sequence.sam_rgb_frames)
        ],
        "parts": [sam_part_payload(spec) for spec in specs],
        "edits": sam3_edits + (edits or []),
        "options": {"maskEncoding": "rle", "confidenceThreshold": 0.25, "maskModel": selected_mask_model},
    }
    try:
        request = urllib.request.Request(
            f"{sam3_url()}/v1/sprite/segment",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=semantic_timeout_seconds()) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        warnings.append(f"semantic skipped: semantic service unavailable ({error})")
        return []

    return tracks_from_response(data, sequence, specs)


def sam_part_payload(spec: SemanticPartSpec) -> dict[str, object]:
    payload = asdict(spec)
    payload.pop("stabilize_settings", None)
    return payload


def tracks_from_response(
    data: dict[str, object], sequence: FrameSequence, specs: list[SemanticPartSpec]
) -> list[PartTrack]:
    specs_by_id = {spec.id: spec for spec in specs}
    tracks: list[PartTrack] = []
    for part_index, item in enumerate(data.get("parts", [])):
        if not isinstance(item, dict):
            continue
        part_id = str(item.get("id", ""))
        spec = specs_by_id.get(part_id)
        if not spec:
            continue
        masks = []
        boxes: list[FrameBox | None] = []
        encoded_masks = item.get("masks", [])
        for frame_index, frame in enumerate(sequence.sam_rgb_frames):
            height, width = int(frame.shape[0]), int(frame.shape[1])
            encoded = (
                encoded_masks[frame_index]
                if frame_index < len(encoded_masks) and isinstance(encoded_masks[frame_index], str)
                else ""
            )
            mask = decode_rle_mask(encoded, width, height)
            source_mask = source_mask_from_semantic_canvas(sequence, frame_index, mask)
            masks.append(source_mask)
            boxes.append(box_from_mask(frame_index, source_mask))
        presence = [bool(value) for value in item.get("presence", [bool(np.any(mask)) for mask in masks])]
        tracks.append(
            PartTrack(
                id=spec.id,
                label=str(item.get("label", spec.label)),
                color=PALETTE[part_index % len(PALETTE)],
                mobility=spec.mobility,
                persistence=spec.persistence,
                confidence=float(item.get("confidence", 0.0) or 0.0),
                masks=masks,
                boxes=boxes,
                warnings=[str(warning) for warning in item.get("warnings", []) if isinstance(warning, str)],
                presence=presence,
                stabilize_settings=dict(spec.stabilize_settings),
            )
        )
    return tracks


def source_mask_from_semantic_canvas(sequence: FrameSequence, frame_index: int, mask: np.ndarray) -> np.ndarray:
    if frame_index < 0 or frame_index >= len(sequence.boxes):
        return mask
    frame = sequence.boxes[frame_index]
    offset_x, offset_y = sequence.semantic_offsets[frame_index]
    out = np.zeros((frame.height, frame.width), dtype=bool)
    x0 = max(0, offset_x)
    y0 = max(0, offset_y)
    x1 = min(mask.shape[1], offset_x + frame.width)
    y1 = min(mask.shape[0], offset_y + frame.height)
    if x1 <= x0 or y1 <= y0:
        return out
    dst_x0 = x0 - offset_x
    dst_y0 = y0 - offset_y
    out[dst_y0 : dst_y0 + (y1 - y0), dst_x0 : dst_x0 + (x1 - x0)] = mask[y0:y1, x0:x1]
    return out


def box_from_mask(index: int, mask: np.ndarray) -> FrameBox | None:
    ys, xs = np.where(mask)
    if ys.size == 0:
        return None
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    return FrameBox(index, x0, y0, x1 - x0, y1 - y0, int(mask.sum()), (x0 + x1) / 2, (y0 + y1) / 2)
