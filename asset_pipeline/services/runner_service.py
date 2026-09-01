from __future__ import annotations

import base64
from io import BytesIO
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict

import numpy as np
import cv2
from PIL import Image

from asset_pipeline.services.chroma_service import distance_alpha, greenscreen_alpha, pixel_alpha
from asset_pipeline.services.config import DEFAULT_WORKERS, PIPELINE_PROFILES, resolved_stage_ids, resolved_stage_map
from asset_pipeline.services.despill_service import neutralize_edge_spill, transparentize_edge_spill
from asset_pipeline.services.frame_service import (
    build_normalized_sheet,
    build_sheet_from_crops,
    detect_frames,
    expand_frames,
    normalized_frame_layout,
)
from asset_pipeline.services.image_ops import crop_to_alpha, crop_with_box, quantized_mode_key, save_png
from asset_pipeline.services.metric_service import evaluate_metrics
from asset_pipeline.services.models import PreviewFiles
from asset_pipeline.services.outline_service import compose_outline, derive_dark_edge_color

from asset_pipeline.services.runner_serialization import (
    part_tracks_debug_metadata,
    scale_crop_box,
    scale_frames,
    scale_metadata_frames,
    scale_part_tracks,
    scale_size,
)
from asset_pipeline.services.part_stabilization_service import (
    compute_semantic_metrics,
    stabilize_parts,
    validate_part_tracks,
)
from asset_pipeline.services.semantic_diagnostics import semantic_metadata
from asset_pipeline.services.rembg_service import rembg_installed, rembg_mask
from asset_pipeline.services.grounding_service import (
    GroundingStageResult,
    grounding_result_metadata,
    grounding_settings_from_options,
    transform_grounding_hints,
)
from asset_pipeline.services.interpolation_client import (
    InterpolationResult,
    interpolate_sequence,
    interpolation_metadata,
    remap_edit_frames,
    remap_editor_part_frames,
    remap_grounding_frames,
)
from asset_pipeline.services.semantic_client import qwen_base_url, segment_parts, semantic_enabled
from asset_pipeline.services.semantic_models import FrameSequence, SemanticMetrics
from asset_pipeline.services.stabilization_service import (
    clean_alpha_islands,
    extrude_sheet_edges,
    flow_guided_deflicker_sheet,
    temporal_deflicker_sheet,
)
from asset_pipeline.services.storage_service import ensure_workspace, safe_source_path
from asset_pipeline.services.upscale_service import upscale_rgba
from asset_pipeline.services.vlm_proposer import propose_parts
from asset_pipeline.services.workspace_service import preview_job_id, reset_preview_dir, require_workspace_id


def configure_cv_threads(thread_count: int | None = None) -> None:
    threads = max(1, int(thread_count or max(1, (os.cpu_count() or DEFAULT_WORKERS) // 2)))
    cv2.setNumThreads(threads)


def init_worker(cv_threads: int) -> None:
    configure_cv_threads(cv_threads)


def memory_preview_storage() -> bool:
    return os.environ.get("ASSET_PIPELINE_PREVIEW_STORAGE", "memory") == "memory"


def png_base64(image: np.ndarray) -> str:
    buffer = BytesIO()
    Image.fromarray(image).save(buffer, format="PNG", compress_level=1)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def build_frame_sequence(
    rgb: np.ndarray,
    detection_rgba: np.ndarray,
    processed_cropped: np.ndarray,
    crop_box: dict[str, int],
    frames: list[object],
    key: tuple[int, int, int],
    upscale_mode: str,
    aura_model: str,
    semantic_input_mode: str = "neutral_matte",
    frame_padding: int = 0,
    stabilize_geometry: bool = True,
) -> FrameSequence:
    raw_rgba = np.dstack([rgb, np.full(rgb.shape[:2], 255, dtype=np.uint8)])
    raw_rgba = upscale_rgba(raw_rgba, upscale_mode, aura_model)
    raw_cropped = crop_with_box(raw_rgba, crop_box)
    detection_cropped = crop_with_box(detection_rgba, crop_box)
    raw_rgb_frames = [
        raw_cropped[frame.y : frame.y + frame.height, frame.x : frame.x + frame.width, :3].copy() for frame in frames
    ]
    base_alpha_frames = [
        detection_cropped[frame.y : frame.y + frame.height, frame.x : frame.x + frame.width, 3].copy()
        for frame in frames
    ]
    final_rgba_frames = [
        processed_cropped[frame.y : frame.y + frame.height, frame.x : frame.x + frame.width, :].copy()
        for frame in frames
    ]
    normalized_size, semantic_offsets = normalized_frame_layout(
        processed_cropped, frames, frame_padding, stabilize_geometry
    )
    canvas_width = normalized_size["width"]
    canvas_height = normalized_size["height"]
    sam_rgb_frames = []
    semantic_alpha_frames = []
    neutral = np.array([128, 128, 128], dtype=np.uint8)
    for raw_frame, alpha, final_frame, (offset_x, offset_y) in zip(
        raw_rgb_frames, base_alpha_frames, final_rgba_frames, semantic_offsets
    ):
        matte = np.empty((canvas_height, canvas_width, 3), dtype=np.uint8)
        matte[:, :] = neutral
        canvas_alpha = np.zeros((canvas_height, canvas_width), dtype=np.uint8)
        target_y = slice(offset_y, offset_y + raw_frame.shape[0])
        target_x = slice(offset_x, offset_x + raw_frame.shape[1])
        visible = alpha > 0
        matte_crop = matte[target_y, target_x, :]
        matte_crop[visible] = raw_frame[visible]
        canvas_alpha[target_y, target_x] = alpha
        if semantic_input_mode == "raw_greenscreen":
            raw_canvas = np.empty((canvas_height, canvas_width, 3), dtype=np.uint8)
            raw_canvas[:, :] = neutral
            raw_canvas[target_y, target_x, :] = raw_frame
            sam_rgb_frames.append(raw_canvas)
        elif semantic_input_mode == "final_processed":
            final_rgb = np.empty((canvas_height, canvas_width, 3), dtype=np.uint8)
            final_rgb[:, :] = neutral
            final_visible = final_frame[:, :, 3] > 0
            final_crop = final_rgb[target_y, target_x, :]
            final_crop[final_visible] = final_frame[:, :, :3][final_visible]
            sam_rgb_frames.append(final_rgb)
        else:
            sam_rgb_frames.append(matte)
        semantic_alpha_frames.append(canvas_alpha)
    return FrameSequence(
        raw_rgb_frames,
        base_alpha_frames,
        semantic_alpha_frames,
        sam_rgb_frames,
        final_rgba_frames,
        frames,
        semantic_offsets,
        key,
    )


def debug_frame_files(sequence: FrameSequence) -> tuple[list[dict[str, object]], dict[str, str]]:
    frames: list[dict[str, object]] = []
    file_data: dict[str, str] = {}
    for index, (raw_frame, alpha_frame, sam_frame, final_frame) in enumerate(
        zip(
            sequence.raw_rgb_frames, sequence.semantic_alpha_frames, sequence.sam_rgb_frames, sequence.final_rgba_frames
        )
    ):
        files = {
            "rawRgb": f"debug/frame-{index:02d}-raw-rgb.png",
            "baseAlpha": f"debug/frame-{index:02d}-base-alpha.png",
            "samRgb": f"debug/frame-{index:02d}-sam-rgb.png",
            "finalRgba": f"debug/frame-{index:02d}-final-rgba.png",
        }
        file_data[files["rawRgb"]] = png_base64(raw_frame)
        file_data[files["baseAlpha"]] = png_base64(alpha_frame)
        file_data[files["samRgb"]] = png_base64(sam_frame)
        file_data[files["finalRgba"]] = png_base64(final_frame)
        frames.append(
            {
                "index": index,
                "width": int(sam_frame.shape[1]),
                "height": int(sam_frame.shape[0]),
                "sourceWidth": int(raw_frame.shape[1]),
                "sourceHeight": int(raw_frame.shape[0]),
                "semanticOffset": {
                    "x": int(sequence.semantic_offsets[index][0]),
                    "y": int(sequence.semantic_offsets[index][1]),
                },
                "files": files,
            }
        )
    return frames, file_data


def replace_frame_crops(base: np.ndarray, frames: list[object], crops: list[np.ndarray]) -> np.ndarray:
    result = base.copy()
    for frame, crop in zip(frames, crops):
        result[frame.y : frame.y + frame.height, frame.x : frame.x + frame.width, :] = crop
    return result


from asset_pipeline.services.runner_options import (
    choose_pipeline,
    choose_profile,
    detection_pipeline_for,
    merge_options,
)


def run_pipeline(
    rgb: np.ndarray, key: tuple[int, int, int], pipeline_id: str, options: dict[str, object], stage_ids: tuple[str, ...]
) -> np.ndarray:
    use_despill = "despill" in stage_ids
    use_outline = "outline" in stage_ids
    despill_alpha_mode = str(options.get("despillAlphaMode", "preserve"))
    despill_alpha_strength = float(options.get("despillAlphaStrength", 0.75))
    if pipeline_id == "distance-classic":
        alpha, fields = distance_alpha(rgb, key, options)
        cleaned = rgb
        if use_despill:
            mode = "gray" if options["neutralizeEdges"] == "auto" else str(options["neutralizeEdges"])
            cleaned = neutralize_edge_spill(
                rgb, alpha, fields, mode, float(options["neutralizeStrength"]) * 0.6, float(options["edgeDarken"]) * 0.6
            )
            if despill_alpha_mode == "spill-transparent":
                alpha = transparentize_edge_spill(alpha, fields, despill_alpha_strength)
        if use_outline:
            outline_color = (
                derive_dark_edge_color(cleaned, alpha)
                if str(options["outlineColorMode"]) == "auto-dark"
                else (20, 20, 20)
            )
            cleaned, alpha = compose_outline(
                cleaned,
                alpha,
                int(options["outlineWidth"]),
                float(options["outlineOpacity"]),
                float(options["outlineBlur"]),
                outline_color,
            )
        return np.dstack([cleaned, alpha])
    if pipeline_id == "pixel-solid":
        alpha, fields = pixel_alpha(rgb, key, options)
        cleaned = rgb
        if use_despill:
            mode = "black" if options["neutralizeEdges"] == "auto" else str(options["neutralizeEdges"])
            cleaned = neutralize_edge_spill(rgb, alpha, fields, mode, float(options["neutralizeStrength"]) * 0.8, 0.0)
            if despill_alpha_mode == "spill-transparent":
                alpha = transparentize_edge_spill(alpha, fields, despill_alpha_strength)
        if use_outline:
            outline_color = (
                derive_dark_edge_color(cleaned, alpha)
                if str(options["outlineColorMode"]) == "auto-dark"
                else (20, 20, 20)
            )
            cleaned, alpha = compose_outline(
                cleaned,
                alpha,
                int(options["outlineWidth"]),
                float(options["outlineOpacity"]),
                float(options["outlineBlur"]),
                outline_color,
            )
        return np.dstack([cleaned, alpha])
    if pipeline_id in {"greenscreen-clean", "outline-ink", "rembg-hybrid"}:
        alpha, fields = greenscreen_alpha(rgb, key, options)
        if pipeline_id == "rembg-hybrid" and "rembg-mask" in stage_ids:
            ai_mask = rembg_mask(rgb)
            if ai_mask is None:
                raise RuntimeError("Pipeline rembg-hybrid requested but rembg is not installed.")
            alpha = np.minimum(
                np.maximum(alpha.astype(np.uint16), ai_mask.astype(np.uint16) // 2), ai_mask.astype(np.uint16)
            ).astype(np.uint8)
        cleaned = rgb
        if use_despill:
            mode = "gray" if options["neutralizeEdges"] == "auto" else str(options["neutralizeEdges"])
            cleaned = neutralize_edge_spill(
                rgb, alpha, fields, mode, float(options["despillStrength"]), float(options["edgeDarken"])
            )
            if despill_alpha_mode == "spill-transparent":
                alpha = transparentize_edge_spill(alpha, fields, despill_alpha_strength)
        if use_outline:
            outline_color = (
                derive_dark_edge_color(cleaned, alpha)
                if str(options["outlineColorMode"]) == "auto-dark"
                else (20, 20, 20)
            )
            cleaned, alpha = compose_outline(
                cleaned,
                alpha,
                int(options["outlineWidth"]),
                float(options["outlineOpacity"]),
                float(options["outlineBlur"]),
                outline_color,
            )
        return np.dstack([cleaned, alpha])
    raise ValueError(f"Unsupported pipeline: {pipeline_id}")


def process_source(
    source_name: str, preview_id: str, raw_options: dict[str, object] | None, requested_pipeline: str | None = None
) -> dict[str, object]:
    ensure_workspace()
    source_path = safe_source_path(source_name)
    safe_preview_id = require_workspace_id(preview_id)
    preview_dir = None if memory_preview_storage() else reset_preview_dir(safe_preview_id)

    started_at = time.perf_counter()
    source_image = Image.open(source_path).convert("RGB")
    rgb = np.array(source_image, dtype=np.uint8)
    key = quantized_mode_key(source_image)
    profile = choose_profile(source_name, raw_options or {})
    pipeline_id = choose_pipeline(profile, requested_pipeline, rembg_installed())
    if pipeline_id not in PIPELINE_PROFILES:
        raise ValueError(f"Unsupported pipeline: {pipeline_id}")
    options = merge_options(raw_options, pipeline_id, source_name)
    stage_map = resolved_stage_map(PIPELINE_PROFILES[pipeline_id], raw_options)
    stage_ids = resolved_stage_ids(PIPELINE_PROFILES[pipeline_id], raw_options)
    detection_pipeline = detection_pipeline_for(pipeline_id, profile)

    detection_options = dict(options)
    detection_options["outlineWidth"] = 0
    detection_stage_ids = tuple(
        stage_id
        for stage_id in resolved_stage_ids(PIPELINE_PROFILES[detection_pipeline], detection_options)
        if stage_id not in {"despill", "outline", "upscale"}
    )
    detection_rgba = run_pipeline(rgb, key, detection_pipeline, detection_options, detection_stage_ids)
    final_rgba = run_pipeline(rgb, key, pipeline_id, options, stage_ids)
    if "alpha-cleanup" in detection_stage_ids:
        detection_rgba = clean_alpha_islands(detection_rgba, options)
    if "alpha-cleanup" in stage_ids:
        final_rgba = clean_alpha_islands(final_rgba, options)

    upscale_mode = str(options["upscaleMode"]) if "upscale" in stage_ids else "none"
    aura_model = str(options["auraModel"])

    detection_cropped, crop_box = crop_to_alpha(detection_rgba, int(options["cropPadding"]))
    processed_cropped = crop_with_box(final_rgba, crop_box)
    frames = detect_frames(detection_cropped[:, :, 3], int(options["minFrameArea"]), int(options["alphaCutoff"]))
    frame_expansion = max(0, int(options["outlineWidth"])) + 1
    if frame_expansion > 0:
        frames = expand_frames(frames, processed_cropped.shape[1], processed_cropped.shape[0], frame_expansion)

    semantic_warnings: list[str] = []
    semantic_tracks = []
    semantic_metrics = SemanticMetrics()
    semantic_raw_tracks = []
    semantic_raw_debug_parts: list[dict[str, object]] = []
    semantic_input_mode = str(options.get("semanticInputMode", "neutral_matte"))
    if semantic_input_mode not in {"neutral_matte", "raw_greenscreen", "final_processed"}:
        semantic_input_mode = "neutral_matte"
    semantic_mask_model = str(
        options.get("semanticMaskModel", os.environ.get("ASSET_PIPELINE_SEMANTIC_MASK_MODEL", "sam3")) or "sam3"
    )
    stabilize_geometry = "geometry-stabilize" in stage_ids
    sequence = build_frame_sequence(
        rgb,
        detection_rgba,
        processed_cropped,
        crop_box,
        frames,
        key,
        "none",
        aura_model,
        semantic_input_mode,
        int(options["framePadding"]),
        stabilize_geometry,
    )
    manual_parts = option_list_of_dicts(options, "semanticManualParts")
    semantic_edits: list[dict[str, object]] = option_list_of_dicts(options, "semanticEdits")
    editor_parts = option_list_of_dicts(options, "semanticEditorParts")
    semantic_propose_enabled = "semantic-propose" in stage_ids
    semantic_segment_enabled = "part-segment-track" in stage_ids
    semantic_stage_enabled = (
        semantic_enabled()
        and semantic_segment_enabled
        and (semantic_propose_enabled or bool(manual_parts) or bool(editor_parts))
    )
    semantic_specs = []
    semantic_grounding_edits: list[dict[str, object]] = []
    semantic_grounding_result = None
    semantic_validated = False
    semantic_stabilized = False
    interpolation_result: InterpolationResult | None = None
    interpolated_render_frames: list[np.ndarray] | None = None
    qwen_cache_info: dict[str, object] = {}
    if semantic_stage_enabled:
        grounding_settings = grounding_settings_from_options(options)
        if editor_parts:
            manual_parts = editor_parts
            semantic_edits = []
        specs = propose_parts(sequence, semantic_warnings, manual_parts, qwen_cache_info)
        if editor_parts:
            qwen_cache_info.update(
                {"enabled": False, "status": "manual_editor", "hit": False, "id": None, "path": None}
            )
        if "frame-interpolate" in stage_ids:
            interpolation_result = interpolate_sequence(sequence, semantic_warnings, loop=True)
            if interpolation_result.enabled:
                sequence = interpolation_result.sequence
                interpolated_render_frames = sequence.final_rgba_frames
                remap_grounding_frames(specs, 2)
                semantic_edits = remap_edit_frames(semantic_edits, interpolation_result.source_frame_count, 2)
                editor_parts = remap_editor_part_frames(editor_parts, interpolation_result.source_frame_count, 2)
        semantic_specs = [asdict(spec) for spec in specs]
        if editor_parts:
            semantic_grounding_edits = editor_part_edits(editor_parts, semantic_warnings)
            semantic_grounding_result = GroundingStageResult(
                semantic_grounding_edits,
                grounding_settings,
                [],
                {
                    "source": "manual_editor",
                    "inputHints": 0,
                    "acceptedHints": 0,
                    "ignoredLowConfidence": 0,
                    "ignoredNoForeground": 0,
                    "reassignedFrames": 0,
                    "projectedEdits": len(semantic_grounding_edits),
                },
            )
        elif "semantic-grounding" in stage_ids:
            semantic_grounding_result = transform_grounding_hints(sequence, specs, grounding_settings)
            semantic_grounding_edits = semantic_grounding_result.edits
            semantic_warnings.extend(semantic_grounding_result.warnings)
        else:
            semantic_grounding_edits = []
        semantic_edits = validate_semantic_edits(sequence, semantic_edits, semantic_warnings, "manual")
        semantic_grounding_edits = validate_semantic_edits(
            sequence, semantic_grounding_edits, semantic_warnings, "grounding"
        )
        semantic_raw_tracks = segment_parts(
            sequence, specs, semantic_warnings, semantic_edits, semantic_grounding_edits, semantic_mask_model
        )
        semantic_raw_debug_parts = part_tracks_debug_metadata(semantic_raw_tracks)
        semantic_tracks = semantic_raw_tracks
        if "part-mask-validate" in stage_ids:
            semantic_tracks = validate_part_tracks(semantic_tracks, sequence)
            semantic_validated = True
        if "part-stabilize" in stage_ids:
            semantic_frames, semantic_tracks, semantic_metrics = stabilize_parts(sequence, semantic_tracks, options)
            if interpolation_result and interpolation_result.enabled:
                interpolated_render_frames = semantic_frames
            else:
                processed_cropped = replace_frame_crops(processed_cropped, frames, semantic_frames)
            semantic_stabilized = True
        else:
            semantic_metrics = compute_semantic_metrics(semantic_tracks)
    else:
        semantic_warnings.append("semantic disabled" if not semantic_enabled() else "semantic stages disabled")

    if interpolated_render_frames is not None:
        sheet, metadata_frames, normalized_size, metric_frames = build_sheet_from_crops(interpolated_render_frames)
        processed_cropped = sheet.copy()
        output_frame_count = len(interpolated_render_frames)
    else:
        sheet, metadata_frames, normalized_size = build_normalized_sheet(
            processed_cropped, frames, int(options["framePadding"]), stabilize_geometry
        )
        metric_frames = frames
        output_frame_count = len(frames)
    stabilization_stats: dict[str, object] = {}
    if "flow-deflicker" in stage_ids:
        sheet, flow_stats = flow_guided_deflicker_sheet(sheet, output_frame_count, normalized_size["width"], options)
        stabilization_stats["flowDeflicker"] = flow_stats
    if "temporal-deflicker" in stage_ids:
        sheet, temporal_stats = temporal_deflicker_sheet(sheet, output_frame_count, normalized_size["width"], options)
        stabilization_stats["temporalDeflicker"] = temporal_stats
    if "edge-extrude" in stage_ids:
        sheet, extrude_stats = extrude_sheet_edges(sheet, output_frame_count, normalized_size["width"], options)
        stabilization_stats["edgeExtrude"] = extrude_stats

    semantic_validated_debug_parts = part_tracks_debug_metadata(semantic_tracks)
    semantic_space = {
        "coordinateSpace": "semantic_input_pre_upscale",
        "width": int(sequence.sam_rgb_frames[0].shape[1]) if sequence.sam_rgb_frames else 0,
        "height": int(sequence.sam_rgb_frames[0].shape[0]) if sequence.sam_rgb_frames else 0,
    }
    pre_upscale_processed_size = {"width": int(processed_cropped.shape[1]), "height": int(processed_cropped.shape[0])}
    pre_upscale_normalized_size = dict(normalized_size)
    pre_upscale_sheet_size = {"width": int(sheet.shape[1]), "height": int(sheet.shape[0])}
    output_scale = {"x": 1.0, "y": 1.0}
    output_tracks = semantic_tracks
    output_crop_box = crop_box
    if upscale_mode != "none":
        before_h, before_w = processed_cropped.shape[:2]
        processed_cropped = upscale_rgba(processed_cropped, upscale_mode, aura_model)
        sheet = upscale_rgba(sheet, upscale_mode, aura_model)
        output_scale = {
            "x": round(float(processed_cropped.shape[1]) / max(1, before_w), 6),
            "y": round(float(processed_cropped.shape[0]) / max(1, before_h), 6),
        }
        metadata_frames = scale_metadata_frames(metadata_frames, output_scale["x"], output_scale["y"])
        normalized_size = scale_size(normalized_size, output_scale["x"], output_scale["y"])
        output_crop_box = scale_crop_box(crop_box, output_scale["x"], output_scale["y"])
        output_tracks = scale_part_tracks(semantic_tracks, output_scale["x"], output_scale["y"])

    metrics = evaluate_metrics(
        processed_cropped, key, scale_frames(metric_frames, output_scale["x"], output_scale["y"]), profile
    )
    if semantic_metrics.part_presence_failures:
        metrics.score = round(float(metrics.score) - semantic_metrics.part_presence_failures * 12.0, 4)
    if semantic_metrics.manual_review_required:
        metrics.score = round(float(metrics.score) - 8.0, 4)

    debug_frames, debug_file_data = debug_frame_files(sequence)
    metadata = {
        "source": source_name,
        "previewId": safe_preview_id,
        "pipelineId": pipeline_id,
        "pipelineProfile": asdict(PIPELINE_PROFILES[pipeline_id]),
        "pipelineStages": stage_map,
        "profile": profile,
        "keyColor": {"r": int(key[0]), "g": int(key[1]), "b": int(key[2])},
        "options": options,
        "cropBox": output_crop_box,
        "normalizedFrameSize": normalized_size,
        "sourceSize": {"width": int(rgb.shape[1]), "height": int(rgb.shape[0])},
        "processedSize": {"width": int(processed_cropped.shape[1]), "height": int(processed_cropped.shape[0])},
        "resolutionContract": {
            "semanticCoordinateSpace": "semantic_input_pre_upscale",
            "outputCoordinateSpace": "output_post_upscale" if upscale_mode != "none" else "semantic_input_pre_upscale",
            "upscaleMode": upscale_mode,
            "outputScale": output_scale,
            "semanticInputSize": semantic_space,
            "preUpscaleProcessedSize": pre_upscale_processed_size,
            "preUpscaleNormalizedFrameSize": pre_upscale_normalized_size,
            "preUpscaleSheetSize": pre_upscale_sheet_size,
        },
        "frames": metadata_frames,
        "frameSequence": {
            "sourceBoxes": [
                {"x": frame.x, "y": frame.y, "width": frame.width, "height": frame.height} for frame in sequence.boxes
            ],
            "semanticOffsets": [
                {"x": int(offset_x), "y": int(offset_y)} for offset_x, offset_y in sequence.semantic_offsets
            ],
        },
        "semantic": semantic_metadata(output_tracks, semantic_metrics, semantic_warnings, semantic_mask_model),
        "semanticDebug": {
            "inputMode": semantic_input_mode,
            "stageEnabled": semantic_stage_enabled,
            "frames": debug_frames,
            "resolutionContract": {
                "coordinateSpace": "semantic_input_pre_upscale",
                "upscaleMode": upscale_mode,
                "outputScale": output_scale,
                "note": "Qwen3/SAM3 receive these pre-upscale sam_rgb_frame images; output preview is scaled after semantic stages.",
            },
            "partSpecs": semantic_specs,
            "qwenGrounding": semantic_specs,
            "groundingStage": grounding_result_metadata(semantic_grounding_result),
            "frameInterpolation": interpolation_metadata(interpolation_result),
            "groundingEdits": semantic_grounding_edits,
            "sam3Edits": semantic_grounding_edits + semantic_edits,
            "manualEdits": semantic_edits,
            "sam3RawParts": semantic_raw_debug_parts,
            "sam3ValidatedParts": semantic_validated_debug_parts,
            "audit": {
                "stageIds": list(stage_ids),
                "detectionPipeline": detection_pipeline,
                "semanticCoordinateSpace": "semantic_input_pre_upscale",
                "outputScale": output_scale,
                "sam3FrameSizes": [
                    {"width": int(frame.shape[1]), "height": int(frame.shape[0])} for frame in sequence.sam_rgb_frames
                ],
                "sam3EditCounts": {
                    "grounding": len(semantic_grounding_edits),
                    "manual": len(semantic_edits),
                    "total": len(semantic_grounding_edits) + len(semantic_edits),
                },
                "sam3Url": os.environ.get("ASSET_PIPELINE_SAM3_URL", "http://localhost:8765"),
                "semanticMaskModel": semantic_mask_model,
                "vlmBaseUrl": qwen_base_url(),
                "sam3RawOutput": True,
                "partMaskValidate": semantic_validated,
                "partStabilize": semantic_stabilized,
                "qwenCache": qwen_cache_info,
                "frameInterpolation": interpolation_metadata(interpolation_result),
                "semanticGrounding": grounding_result_metadata(semantic_grounding_result),
            },
        },
        "metrics": asdict(metrics),
        "stabilization": stabilization_stats,
        "durationMs": int((time.perf_counter() - started_at) * 1000),
        "previewFiles": asdict(PreviewFiles("processed.png", "alpha.png", "sheet.png", "metadata.json")),
    }
    if preview_dir:
        save_png(preview_dir / "source.png", rgb)
        save_png(preview_dir / "processed.png", processed_cropped)
        save_png(preview_dir / "alpha.png", processed_cropped[:, :, 3])
        save_png(preview_dir / "sheet.png", sheet)
        (preview_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        for filename, encoded in debug_file_data.items():
            target = preview_dir / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(encoded))
    else:
        metadata["previewFileData"] = {
            "source.png": png_base64(rgb),
            "processed.png": png_base64(processed_cropped),
            "alpha.png": png_base64(processed_cropped[:, :, 3]),
            "sheet.png": png_base64(sheet),
            **debug_file_data,
        }
    return metadata


def compare_pipelines(
    source_name: str,
    batch_id: str,
    raw_options: dict[str, object] | None,
    pipeline_ids: list[str] | None,
    workers: int | None,
) -> dict[str, object]:
    return compare_matrix([source_name], batch_id, raw_options, pipeline_ids, workers)


def compare_matrix(
    source_names: list[str],
    batch_id: str,
    raw_options: dict[str, object] | None,
    pipeline_ids: list[str] | None,
    workers: int | None,
) -> dict[str, object]:
    if not source_names:
        raise ValueError("At least one source is required.")
    enabled = [profile.id for profile in PIPELINE_PROFILES.values() if profile.optional != "rembg" or rembg_installed()]
    selected = pipeline_ids or enabled
    disabled = sorted(set(selected) - set(enabled))
    if disabled:
        raise ValueError(f"Pipelines are unavailable: {disabled}")
    if not selected:
        raise ValueError("No enabled pipelines selected.")
    jobs = [(source_name, pipeline_id) for source_name in source_names for pipeline_id in selected]
    max_workers = max(1, min(int(workers or DEFAULT_WORKERS), len(jobs), os.cpu_count() or DEFAULT_WORKERS))
    started_at = time.perf_counter()
    results: list[dict[str, object]] = []
    base_options = dict(raw_options or {})
    pipeline_options = base_options.pop("pipelineOptions", {})
    if not isinstance(pipeline_options, dict):
        pipeline_options = {}

    cv_threads = max(1, (os.cpu_count() or DEFAULT_WORKERS) // max_workers)
    with ProcessPoolExecutor(max_workers=max_workers, initializer=init_worker, initargs=(cv_threads,)) as executor:
        futures = {
            executor.submit(
                process_source,
                source_name,
                preview_job_id(batch_id, source_name, pipeline_id),
                {**base_options, **options_for_pipeline(pipeline_options, pipeline_id)},
                pipeline_id,
            ): (source_name, pipeline_id)
            for source_name, pipeline_id in jobs
        }
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: (item["source"], -item["metrics"]["score"]))
    return {
        "source": source_names[0] if len(source_names) == 1 else None,
        "sources": source_names,
        "batchId": batch_id,
        "workers": max_workers,
        "durationMs": int((time.perf_counter() - started_at) * 1000),
        "results": results,
    }


def options_for_pipeline(pipeline_options: dict[str, object], pipeline_id: str) -> dict[str, object]:
    options = pipeline_options.get(pipeline_id, {})
    if not isinstance(options, dict):
        raise ValueError(f"Pipeline options must be an object: {pipeline_id}")
    return options


def option_list_of_dicts(options: dict[str, object], key: str) -> list[dict[str, object]]:
    value = options.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def validate_semantic_edits(
    sequence: FrameSequence,
    edits: list[dict[str, object]],
    warnings: list[str],
    source: str,
) -> list[dict[str, object]]:
    valid: list[dict[str, object]] = []
    for edit in edits:
        try:
            frame_index = int(edit.get("frame", -1))
        except (TypeError, ValueError):
            warnings.append(f"semantic {source} edit ignored: invalid frame")
            continue
        if frame_index < 0 or frame_index >= len(sequence.sam_rgb_frames):
            warnings.append(f"semantic {source} edit ignored: frame {frame_index} out of range")
            continue
        frame = sequence.sam_rgb_frames[frame_index]
        height, width = int(frame.shape[0]), int(frame.shape[1])
        space = edit.get("space")
        if isinstance(space, dict):
            try:
                space_width = int(space.get("frameWidth", 0))
                space_height = int(space.get("frameHeight", 0))
            except (TypeError, ValueError):
                space_width = 0
                space_height = 0
            if space_width and space_height and (space_width != width or space_height != height):
                warnings.append(
                    f"semantic {source} edit ignored: coordinate space {space_width}x{space_height} != current {width}x{height}"
                )
                continue
        normalized = normalize_semantic_edit(edit, width, height, warnings, source)
        if normalized is not None:
            valid.append(normalized)
    return valid


def normalize_semantic_edit(
    edit: dict[str, object],
    width: int,
    height: int,
    warnings: list[str],
    source: str,
) -> dict[str, object] | None:
    edit_type = edit.get("type")
    normalized = dict(edit)
    normalized.pop("space", None)
    if edit_type == "bbox":
        box = edit.get("box")
        if not (isinstance(box, list) and len(box) == 4):
            warnings.append(f"semantic {source} edit ignored: invalid bbox")
            return None
        try:
            x0, y0, x1, y1 = [float(value) for value in box]
        except (TypeError, ValueError):
            warnings.append(f"semantic {source} edit ignored: invalid bbox")
            return None
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        if x1 <= 0 or y1 <= 0 or x0 >= width or y0 >= height:
            warnings.append(f"semantic {source} edit ignored: bbox outside frame")
            return None
        normalized["box"] = [
            int(round(max(0.0, min(float(width - 1), x0)))),
            int(round(max(0.0, min(float(height - 1), y0)))),
            int(round(max(1.0, min(float(width), x1)))),
            int(round(max(1.0, min(float(height), y1)))),
        ]
        return normalized
    if edit_type in {"positive_point", "negative_point"}:
        try:
            x = float(edit.get("x"))
            y = float(edit.get("y"))
        except (TypeError, ValueError):
            warnings.append(f"semantic {source} edit ignored: invalid point")
            return None
        if x < 0 or y < 0 or x >= width or y >= height:
            warnings.append(f"semantic {source} edit ignored: point outside frame")
            return None
        normalized["x"] = int(round(x))
        normalized["y"] = int(round(y))
        return normalized
    warnings.append(f"semantic {source} edit ignored: invalid type")
    return None


def editor_part_edits(parts: list[dict[str, object]], warnings: list[str]) -> list[dict[str, object]]:
    edits: list[dict[str, object]] = []
    for part in parts:
        part_id = str(part.get("id", "")).strip()
        raw_edits = part.get("edits", [])
        if not part_id or not isinstance(raw_edits, list):
            continue
        for item in raw_edits:
            if not isinstance(item, dict):
                continue
            edit = dict(item)
            edit["partId"] = part_id
            edit_type = edit.get("type")
            if edit_type == "bbox" and isinstance(edit.get("box"), list) and len(edit["box"]) == 4:
                edits.append(edit)
            elif (
                edit_type in {"positive_point", "negative_point"}
                and isinstance(edit.get("x"), (int, float))
                and isinstance(edit.get("y"), (int, float))
            ):
                edits.append(edit)
            else:
                warnings.append(f"semantic editor ignored invalid edit for {part_id}")
    return edits
