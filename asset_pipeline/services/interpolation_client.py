from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from io import BytesIO
import json
import os
import urllib.error
import urllib.request

import numpy as np
from PIL import Image

from asset_pipeline.services.models import FrameBox
from asset_pipeline.services.semantic_models import FrameSequence, SemanticPartSpec


@dataclass
class InterpolationResult:
    sequence: FrameSequence
    enabled: bool
    status: str
    source_frame_count: int
    output_frame_count: int
    model: str
    loop: bool
    error: str | None = None


def interpolation_url() -> str:
    return os.environ.get("ASSET_PIPELINE_INTERPOLATION_URL", "http://localhost:8775").rstrip("/")


def interpolation_timeout_seconds() -> float:
    return max(1.0, int(os.environ.get("ASSET_PIPELINE_INTERPOLATION_TIMEOUT_MS", "300000")) / 1000.0)


def encode_png_base64(image: np.ndarray) -> str:
    buffer = BytesIO()
    Image.fromarray(image.astype(np.uint8), mode="RGBA").save(buffer, format="PNG", compress_level=1)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def decode_png_base64(encoded: str) -> np.ndarray:
    return np.asarray(Image.open(BytesIO(base64.b64decode(encoded))).convert("RGBA"), dtype=np.uint8)


def normalized_rgba_frames(sequence: FrameSequence) -> list[np.ndarray]:
    if not sequence.sam_rgb_frames:
        return []
    height, width = sequence.sam_rgb_frames[0].shape[:2]
    frames: list[np.ndarray] = []
    for crop, (offset_x, offset_y) in zip(sequence.final_rgba_frames, sequence.semantic_offsets):
        canvas = np.zeros((height, width, 4), dtype=np.uint8)
        target = canvas[offset_y : offset_y + crop.shape[0], offset_x : offset_x + crop.shape[1], :]
        target[:] = crop
        frames.append(canvas)
    return frames


def frame_box(index: int, alpha: np.ndarray) -> FrameBox:
    ys, xs = np.where(alpha > 0)
    if not len(xs):
        return FrameBox(index, 0, 0, alpha.shape[1], alpha.shape[0], 0, alpha.shape[1] / 2, alpha.shape[0] / 2)
    return FrameBox(index, 0, 0, alpha.shape[1], alpha.shape[0], int(len(xs)), float(xs.mean()), float(ys.mean()))


def sequence_from_rgba(sequence: FrameSequence, frames: list[np.ndarray]) -> FrameSequence:
    matte = np.asarray([128, 128, 128], dtype=np.uint8)
    rgb_frames: list[np.ndarray] = []
    alpha_frames: list[np.ndarray] = []
    boxes: list[FrameBox] = []
    for index, rgba in enumerate(frames):
        alpha = rgba[:, :, 3].copy()
        rgb = rgba[:, :, :3].copy()
        rgb[alpha == 0] = matte
        rgb_frames.append(rgb)
        alpha_frames.append(alpha)
        boxes.append(frame_box(index, alpha))
    return FrameSequence(
        raw_rgb_frames=[frame.copy() for frame in rgb_frames],
        base_alpha_frames=[alpha.copy() for alpha in alpha_frames],
        semantic_alpha_frames=[alpha.copy() for alpha in alpha_frames],
        sam_rgb_frames=rgb_frames,
        final_rgba_frames=frames,
        boxes=boxes,
        semantic_offsets=[(0, 0)] * len(frames),
        key_color=sequence.key_color,
    )


def interpolate_sequence(sequence: FrameSequence, warnings: list[str], loop: bool = True) -> InterpolationResult:
    source_frames = normalized_rgba_frames(sequence)
    source_count = len(source_frames)
    if not 2 <= source_count <= 16:
        message = f"frame interpolation skipped: expected 2-16 frames, got {source_count}"
        warnings.append(message)
        return InterpolationResult(
            sequence, False, "skipped", source_count, source_count, "practical-rife-4.25", loop, message
        )
    height, width = source_frames[0].shape[:2]
    payload = {
        "frames": [
            {"index": index, "width": width, "height": height, "rgbaPngBase64": encode_png_base64(frame)}
            for index, frame in enumerate(source_frames)
        ],
        "options": {"factor": 2, "loop": loop, "alphaMode": "rife", "matteColor": [128, 128, 128], "scale": 1.0},
    }
    try:
        request = urllib.request.Request(
            f"{interpolation_url()}/v1/sprite/interpolate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=interpolation_timeout_seconds()) as response:
            data = json.loads(response.read().decode("utf-8"))
        output = [decode_png_base64(item["rgbaPngBase64"]) for item in data.get("frames", [])]
        expected = source_count * 2 if loop else source_count * 2 - 1
        if len(output) != expected:
            raise ValueError(f"service returned {len(output)} frames, expected {expected}")
        return InterpolationResult(
            sequence_from_rgba(sequence, output), True, "ready", source_count, len(output), "practical-rife-4.25", loop
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        OSError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
    ) as error:
        message = f"frame interpolation skipped: service unavailable ({error})"
        warnings.append(message)
        return InterpolationResult(
            sequence, False, "unavailable", source_count, source_count, "practical-rife-4.25", loop, str(error)
        )


def remap_grounding_frames(specs: list[SemanticPartSpec], factor: int = 2) -> None:
    for spec in specs:
        spec.grounding = [replace(hint, frame=hint.frame * factor) for hint in spec.grounding]


def remap_edit_frames(
    edits: list[dict[str, object]],
    source_frame_count: int,
    factor: int = 2,
) -> list[dict[str, object]]:
    output_frame_count = source_frame_count * factor
    remapped: list[dict[str, object]] = []
    for edit in edits:
        next_edit = dict(edit)
        space = edit.get("space")
        authored_frame_count = space.get("frameCount") if isinstance(space, dict) else None
        try:
            frame_index = int(edit.get("frame", -1))
            authored_count = int(authored_frame_count) if authored_frame_count is not None else None
        except (TypeError, ValueError):
            remapped.append(next_edit)
            continue
        is_source_timebase = authored_count in {None, source_frame_count}
        if is_source_timebase and 0 <= frame_index < source_frame_count:
            next_edit["frame"] = frame_index * factor
        elif authored_count == output_frame_count:
            next_edit["frame"] = frame_index
        remapped.append(next_edit)
    return remapped


def remap_editor_part_frames(
    parts: list[dict[str, object]],
    source_frame_count: int,
    factor: int = 2,
) -> list[dict[str, object]]:
    remapped: list[dict[str, object]] = []
    for part in parts:
        next_part = dict(part)
        edits = part.get("edits", [])
        if isinstance(edits, list):
            next_part["edits"] = remap_edit_frames(
                [edit for edit in edits if isinstance(edit, dict)], source_frame_count, factor
            )
        remapped.append(next_part)
    return remapped


def interpolation_metadata(result: InterpolationResult | None) -> dict[str, object]:
    if result is None:
        return {"enabled": False, "status": "disabled", "factor": 2}
    return {
        "enabled": result.enabled,
        "status": result.status,
        "factor": 2,
        "loop": result.loop,
        "model": result.model,
        "sourceFrameCount": result.source_frame_count,
        "outputFrameCount": result.output_frame_count,
        "url": interpolation_url(),
        "error": result.error,
    }
