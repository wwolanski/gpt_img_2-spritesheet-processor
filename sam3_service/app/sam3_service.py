from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from contextlib import nullcontext
from pathlib import Path
from threading import Lock

import cv2
import numpy as np
from PIL import Image

from app.mask_codec import decode_png_base64, encode_rle_mask
from app.mask_geometry import (
    box_iou,
    box_xyxy_from_mask,
    clamp_box_xyxy,
    draw_trimap_disk,
    expand_box_xyxy,
    latest_bbox_edit,
    points_match_mask,
    prompt_tokens,
)
from app.schemas import PartEdit, SegmentPartResult, SegmentRequest, SemanticPartSpec

SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = SERVICE_ROOT / "models" / "sam3.1_multiplex_fp16.safetensors"
DEFAULT_YOLO26_MODEL_PATH = SERVICE_ROOT / "models" / "yolo26x-seg.pt"
DEFAULT_VITMATTE_MODEL_PATH = SERVICE_ROOT / "models" / "vitmatte-small-composition-1k"
SUPPORTED_MASK_MODELS = ("sam3", "yolo26", "vitmatte", "inspirinet")
LOGGER = logging.getLogger("sam3_service")


@dataclass
class Sam3Runtime:
    name: str
    provider: str
    model_path: str
    device: str
    half: bool
    imgsz: int
    model: object | None = None
    semantic_predictor: object | None = None
    processor: object | None = None
    warnings: list[str] | None = None
    lock: object = None


def fallback_masks_enabled() -> bool:
    return os.environ.get("SAM3_FALLBACK_MASKS", "0") == "1"


def default_mask_model() -> str:
    return normalize_mask_model(os.environ.get("SEMANTIC_MASK_MODEL", "sam3"))


def normalize_mask_model(mask_model: str | None) -> str:
    value = (mask_model or "").strip().lower().replace("_", "-")
    aliases = {
        "sam": "sam3",
        "sam-3": "sam3",
        "yolo": "yolo26",
        "yolo-26": "yolo26",
        "yolo26-seg": "yolo26",
        "yolo26n-seg": "yolo26",
        "inspirinet": "inspirinet",
        "inspyrenet": "inspirinet",
        "vit-matte": "vitmatte",
        "vitmatte": "vitmatte",
    }
    return aliases.get(value, value if value in SUPPORTED_MASK_MODELS else "sam3")


def load_runtime(mask_model: str | None = None) -> Sam3Runtime:
    name = normalize_mask_model(mask_model or default_mask_model())
    LOGGER.info("runtime load requested: mask_model=%s", name)
    if name == "yolo26":
        return load_yolo26_runtime()
    if name == "vitmatte":
        return load_vitmatte_runtime()
    if name == "inspirinet":
        return unavailable_runtime(name, f"{name} provider not implemented yet")
    return load_sam3_runtime()


def load_sam3_runtime() -> Sam3Runtime:
    original_model_path = os.environ.get("SAM3_MODEL_PATH", str(DEFAULT_MODEL_PATH))
    LOGGER.info(
        "loading model: mask_model=sam3 provider=asset-pipeline-sam3 path=%s device=%s half=%s imgsz=%s",
        original_model_path,
        os.environ.get("SAM3_DEVICE", "cuda"),
        os.environ.get("SAM3_HALF", "1"),
        sam3_imgsz(),
    )
    runtime = Sam3Runtime(
        name="sam3",
        provider="asset-pipeline-sam3",
        model_path=original_model_path,
        device=os.environ.get("SAM3_DEVICE", "cuda"),
        half=os.environ.get("SAM3_HALF", "1") == "1",
        imgsz=sam3_imgsz(),
        warnings=[],
        lock=Lock(),
    )
    try:
        os.environ.setdefault("YOLO_VERBOSE", "False")
        model_path = prepare_ultralytics_model_path(Path(original_model_path))
        from ultralytics.models.sam import SAM3SemanticPredictor
        from ultralytics.utils import LOGGER as ULTRALYTICS_LOGGER

        ULTRALYTICS_LOGGER.setLevel(os.environ.get("SAM3_ULTRALYTICS_LOG_LEVEL", "ERROR"))
        runtime.semantic_predictor = SAM3SemanticPredictor(
            overrides={
                "conf": 0.25,
                "iou": 0.7,
                "task": "segment",
                "mode": "predict",
                "model": str(model_path),
                "half": runtime.half,
                "imgsz": runtime.imgsz,
                "save": False,
                "device": runtime.device,
                "verbose": False,
            }
        )
        runtime.semantic_predictor.setup_model(verbose=False)
        LOGGER.info("model loaded: mask_model=sam3 path=%s", original_model_path)
    except Exception as error:  # pragma: no cover - depends on local GPU/model image.
        runtime.model = None
        runtime.semantic_predictor = None
        runtime.warnings = [f"SAM3 unavailable: {error}"]
        LOGGER.exception("model load failed: mask_model=sam3 path=%s", original_model_path)
        clear_cuda_cache()
    return runtime


def load_yolo26_runtime() -> Sam3Runtime:
    model_path = os.environ.get("YOLO26_MODEL_PATH", str(DEFAULT_YOLO26_MODEL_PATH))
    LOGGER.info(
        "loading model: mask_model=yolo26 provider=asset-pipeline-yolo26 path=%s device=%s half=%s imgsz=%s",
        model_path,
        os.environ.get("YOLO26_DEVICE", os.environ.get("SAM3_DEVICE", "cuda")),
        os.environ.get("YOLO26_HALF", os.environ.get("SAM3_HALF", "1")),
        yolo26_imgsz(),
    )
    runtime = Sam3Runtime(
        name="yolo26",
        provider="asset-pipeline-yolo26",
        model_path=model_path,
        device=os.environ.get("YOLO26_DEVICE", os.environ.get("SAM3_DEVICE", "cuda")),
        half=os.environ.get("YOLO26_HALF", os.environ.get("SAM3_HALF", "1")) == "1",
        imgsz=yolo26_imgsz(),
        warnings=[],
        lock=Lock(),
    )
    try:
        os.environ.setdefault("YOLO_VERBOSE", "False")
        from ultralytics import YOLO
        from ultralytics.utils import LOGGER as ULTRALYTICS_LOGGER

        ULTRALYTICS_LOGGER.setLevel(os.environ.get("YOLO26_ULTRALYTICS_LOG_LEVEL", "ERROR"))
        runtime.model = YOLO(model_path)
        LOGGER.info("model loaded: mask_model=yolo26 path=%s", model_path)
    except Exception as error:  # pragma: no cover - depends on local GPU/model image.
        runtime.model = None
        runtime.warnings = [f"YOLO26 unavailable: {error}"]
        LOGGER.exception("model load failed: mask_model=yolo26 path=%s", model_path)
        clear_cuda_cache()
    return runtime


def load_vitmatte_runtime() -> Sam3Runtime:
    model_path = os.environ.get("VITMATTE_MODEL_PATH", str(DEFAULT_VITMATTE_MODEL_PATH))
    device = os.environ.get("VITMATTE_DEVICE", os.environ.get("SAM3_DEVICE", "cuda"))
    half = os.environ.get("VITMATTE_HALF", os.environ.get("SAM3_HALF", "1")) == "1"
    LOGGER.info(
        "loading model: mask_model=vitmatte provider=asset-pipeline-vitmatte path=%s device=%s half=%s",
        model_path,
        device,
        int(half),
    )
    runtime = Sam3Runtime(
        name="vitmatte",
        provider="asset-pipeline-vitmatte",
        model_path=model_path,
        device=device,
        half=half,
        imgsz=0,
        warnings=[],
        lock=Lock(),
    )
    try:
        import torch
        from transformers import VitMatteForImageMatting, VitMatteImageProcessor

        runtime.processor = VitMatteImageProcessor()
        runtime.model = VitMatteForImageMatting.from_pretrained(model_path).eval()
        if device != "cpu" and torch.cuda.is_available():
            runtime.model = runtime.model.to(device)
            if half:
                runtime.model = runtime.model.half()
        else:
            runtime.device = "cpu"
            runtime.half = False
        LOGGER.info(
            "model loaded: mask_model=vitmatte path=%s device=%s half=%s", model_path, runtime.device, int(runtime.half)
        )
    except Exception as error:  # pragma: no cover - depends on local GPU/model image.
        runtime.model = None
        runtime.processor = None
        runtime.warnings = [f"ViTMatte unavailable: {error}"]
        LOGGER.exception("model load failed: mask_model=vitmatte path=%s", model_path)
        clear_cuda_cache()
    return runtime


def unavailable_runtime(name: str, warning: str) -> Sam3Runtime:
    LOGGER.warning("runtime unavailable: mask_model=%s warning=%s", name, warning)
    return Sam3Runtime(
        name=name,
        provider=f"asset-pipeline-{name}",
        model_path="",
        device=os.environ.get("SAM3_DEVICE", "cuda"),
        half=False,
        imgsz=0,
        warnings=[warning],
        lock=Lock(),
    )


def unload_runtime(runtime: Sam3Runtime | None) -> None:
    if runtime is None:
        return
    LOGGER.info(
        "unloading model: mask_model=%s provider=%s path=%s", runtime.name, runtime.provider, runtime.model_path
    )
    try:
        predictor = runtime.semantic_predictor
        if predictor is not None:
            try:
                predictor.reset_image()
            except Exception:
                pass
        runtime.semantic_predictor = None
        runtime.processor = None
        runtime.model = None
    finally:
        clear_cuda_cache()
        LOGGER.info("model unloaded: mask_model=%s", runtime.name)


def sam3_imgsz() -> int:
    try:
        value = int(os.environ.get("SAM3_IMGSZ", "644"))
    except ValueError:
        value = 644
    return max(14, ((value + 13) // 14) * 14)


def yolo26_imgsz() -> int:
    try:
        value = int(os.environ.get("YOLO26_IMGSZ", "640"))
    except ValueError:
        value = 640
    return max(32, ((value + 31) // 32) * 32)


def prepare_ultralytics_model_path(model_path: Path) -> Path:
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if model_path.suffix in {".pt", ".pth"}:
        return model_path
    if model_path.suffix != ".safetensors":
        raise ValueError(f"Unsupported SAM3 model format: {model_path.suffix}")
    return convert_safetensors_to_pt(model_path)


def convert_safetensors_to_pt(model_path: Path) -> Path:
    cache_dir = model_path.parent / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    stat = model_path.stat()
    cache_path = cache_dir / f"{model_path.stem}.{stat.st_size}.{int(stat.st_mtime)}.pt"
    if cache_path.exists():
        return cache_path

    from safetensors.torch import load_file
    import torch

    state_dict: dict[str, object] = load_file(str(model_path), device="cpu")
    temp_path = cache_path.with_suffix(".tmp")
    torch.save({"model": state_dict}, temp_path)
    temp_path.replace(cache_path)
    return cache_path


def segment_sprite(runtime: Sam3Runtime, request: SegmentRequest) -> list[SegmentPartResult]:
    edit_counts = edit_type_counts(request.edits)
    LOGGER.info(
        "segment request start: mask_model=%s frames=%s parts=%s prompt_edits=%s edit_types=%s confidence_threshold=%.3f",
        runtime.name,
        len(request.frames),
        len(request.parts),
        len(request.edits),
        edit_counts,
        request.options.confidenceThreshold,
    )
    frames = [decode_png_base64(frame.rgbPngBase64) for frame in request.frames]
    state: dict[str, dict[str, object]] = {
        part.id: {"masks": [], "boxes": [], "warnings": list(runtime.warnings or []), "confidences": []}
        for part in request.parts
    }
    edits_by_frame_part: dict[tuple[int, str], list[PartEdit]] = {}
    for edit in request.edits:
        edits_by_frame_part.setdefault((edit.frame, edit.partId), []).append(edit)

    lock = runtime.lock
    with lock if lock is not None else nullcontext():
        for frame_index, frame in enumerate(frames):
            LOGGER.info(
                "segment frame start: mask_model=%s frame=%s size=%sx%s parts=%s",
                runtime.name,
                frame_index,
                frame.shape[1],
                frame.shape[0],
                len(request.parts),
            )
            frame_results = segment_frame_parts(
                runtime,
                frame,
                request.parts,
                {part.id: edits_by_frame_part.get((frame_index, part.id), []) for part in request.parts},
                request.options.confidenceThreshold,
            )
            for part in request.parts:
                mask, confidence, call_warnings = frame_results[part.id]
                part_state = state[part.id]
                part_state["warnings"].extend(call_warnings)
                part_state["masks"].append(mask)
                part_state["boxes"].append(box_from_mask(mask))
                part_state["confidences"].append(confidence)
            LOGGER.info("segment frame done: mask_model=%s frame=%s", runtime.name, frame_index)

    results: list[SegmentPartResult] = []
    for part in request.parts:
        part_state = state[part.id]
        masks = part_state["masks"]
        confidences = part_state["confidences"]
        result = SegmentPartResult(
            id=part.id,
            label=part.label,
            confidence=float(np.mean(confidences)) if confidences else 0.0,
            presence=[bool(mask.any()) for mask in masks],
            boxes=part_state["boxes"],
            masks=[encode_rle_mask(mask) for mask in masks],
            warnings=dedupe_warnings(part_state["warnings"]),
        )
        LOGGER.info(
            "segment part done: mask_model=%s part=%s confidence=%.4f present_frames=%s warnings=%s",
            runtime.name,
            part.id,
            result.confidence,
            sum(1 for present in result.presence if present),
            len(result.warnings),
        )
        results.append(result)
    LOGGER.info("segment request done: mask_model=%s parts=%s", runtime.name, len(results))
    return results


def edit_type_counts(edits: list[PartEdit]) -> dict[str, int]:
    counts = {"bbox": 0, "positive_point": 0, "negative_point": 0}
    for edit in edits:
        counts[edit.type] = counts.get(edit.type, 0) + 1
    return counts


def segment_frame(
    runtime: Sam3Runtime,
    rgb: np.ndarray,
    prompt: str,
    edits: list[PartEdit],
    confidence_threshold: float,
) -> tuple[np.ndarray, float, list[str]]:
    part = SemanticPartSpec(id="_part", label="_part", prompt=prompt, mobility="medium", persistence="always")
    return segment_frame_parts(runtime, rgb, [part], {part.id: edits}, confidence_threshold)[part.id]


def segment_frame_parts(
    runtime: Sam3Runtime,
    rgb: np.ndarray,
    parts: list[SemanticPartSpec],
    edits_by_part: dict[str, list[PartEdit]],
    confidence_threshold: float,
) -> dict[str, tuple[np.ndarray, float, list[str]]]:
    if runtime.name == "yolo26":
        return segment_frame_parts_yolo26(runtime, rgb, parts, edits_by_part, confidence_threshold)
    if runtime.name == "vitmatte":
        return segment_frame_parts_vitmatte(runtime, rgb, parts, edits_by_part, confidence_threshold)
    if runtime.name != "sam3":
        return unavailable_frame_parts(runtime, rgb, parts)
    return segment_frame_parts_sam3(runtime, rgb, parts, edits_by_part, confidence_threshold)


def unavailable_frame_parts(
    runtime: Sam3Runtime,
    rgb: np.ndarray,
    parts: list[SemanticPartSpec],
) -> dict[str, tuple[np.ndarray, float, list[str]]]:
    warning = (runtime.warnings or [f"{runtime.name} runtime unavailable"])[0]
    return {part.id: (np.zeros(rgb.shape[:2], dtype=bool), 0.0, [warning]) for part in parts}


def segment_frame_parts_sam3(
    runtime: Sam3Runtime,
    rgb: np.ndarray,
    parts: list[SemanticPartSpec],
    edits_by_part: dict[str, list[PartEdit]],
    confidence_threshold: float,
) -> dict[str, tuple[np.ndarray, float, list[str]]]:
    if runtime.semantic_predictor is None:
        if fallback_masks_enabled():
            return {part.id: (fallback_semantic_mask(rgb), 0.35, []) for part in parts}
        return {
            part.id: (np.zeros(rgb.shape[:2], dtype=bool), 0.0, ["SAM3 inference skipped: runtime unavailable"])
            for part in parts
        }

    shape = rgb.shape[:2]
    output: dict[str, tuple[np.ndarray, float, list[str]]] = {}
    predictor = runtime.semantic_predictor
    try:
        predictor.set_image(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        text_parts: list[SemanticPartSpec] = []
        for part in parts:
            visual_result = run_visual_prompt(predictor, shape, edits_by_part.get(part.id, []))
            if visual_result is None:
                text_parts.append(part)
            else:
                output[part.id] = (visual_result[0], visual_result[1], [])

        if text_parts:
            pred_masks, pred_boxes = predictor.inference_features(
                predictor.features,
                shape,
                text=[part.prompt for part in text_parts],
            )
            LOGGER.info("sam3 text inference done: text_parts=%s shape=%sx%s", len(text_parts), shape[1], shape[0])
            for class_index, part in enumerate(text_parts):
                mask, confidence = mask_from_prediction_tensors(
                    pred_masks,
                    pred_boxes,
                    shape,
                    confidence_threshold,
                    class_index=class_index,
                )
                output[part.id] = (mask, confidence, [])
        LOGGER.info("sam3 inference done: parts=%s shape=%sx%s", len(output), shape[1], shape[0])
        return output
    except Exception as error:  # pragma: no cover - depends on SAM3 runtime.
        clear_cuda_cache()
        warning = f"SAM3 inference failed: {error}"
        if fallback_masks_enabled():
            return {part.id: (fallback_semantic_mask(rgb), 0.25, [warning]) for part in parts}
        return {part.id: (np.zeros(shape, dtype=bool), 0.0, [warning]) for part in parts}
    finally:
        try:
            predictor.reset_image()
        except Exception:
            pass


def segment_frame_parts_yolo26(
    runtime: Sam3Runtime,
    rgb: np.ndarray,
    parts: list[SemanticPartSpec],
    edits_by_part: dict[str, list[PartEdit]],
    confidence_threshold: float,
) -> dict[str, tuple[np.ndarray, float, list[str]]]:
    if runtime.model is None:
        if fallback_masks_enabled():
            return {part.id: (fallback_semantic_mask(rgb), 0.35, list(runtime.warnings or [])) for part in parts}
        return {
            part.id: (np.zeros(rgb.shape[:2], dtype=bool), 0.0, ["YOLO26 inference skipped: runtime unavailable"])
            for part in parts
        }

    shape = rgb.shape[:2]
    try:
        results = runtime.model.predict(
            source=rgb,
            conf=confidence_threshold,
            imgsz=runtime.imgsz,
            device=runtime.device,
            half=runtime.half,
            verbose=False,
        )
        candidates = yolo_candidates(results, shape, runtime.model)
        LOGGER.info("yolo26 inference done: candidates=%s shape=%sx%s", len(candidates), shape[1], shape[0])
        output: dict[str, tuple[np.ndarray, float, list[str]]] = {}
        for part in parts:
            mask, confidence, warnings = select_yolo_mask_for_part(
                part,
                candidates,
                edits_by_part.get(part.id, []),
                shape,
                confidence_threshold,
            )
            output[part.id] = (mask, confidence, warnings)
        return output
    except Exception as error:  # pragma: no cover - depends on YOLO runtime.
        clear_cuda_cache()
        warning = f"YOLO26 inference failed: {error}"
        if fallback_masks_enabled():
            return {part.id: (fallback_semantic_mask(rgb), 0.25, [warning]) for part in parts}
        return {part.id: (np.zeros(shape, dtype=bool), 0.0, [warning]) for part in parts}


def segment_frame_parts_vitmatte(
    runtime: Sam3Runtime,
    rgb: np.ndarray,
    parts: list[SemanticPartSpec],
    edits_by_part: dict[str, list[PartEdit]],
    confidence_threshold: float,
) -> dict[str, tuple[np.ndarray, float, list[str]]]:
    if runtime.model is None or runtime.processor is None:
        if fallback_masks_enabled():
            return {part.id: (fallback_semantic_mask(rgb), 0.35, list(runtime.warnings or [])) for part in parts}
        return {
            part.id: (np.zeros(rgb.shape[:2], dtype=bool), 0.0, ["ViTMatte inference skipped: runtime unavailable"])
            for part in parts
        }

    try:
        import torch

        image = Image.fromarray(rgb, mode="RGB")
        output: dict[str, tuple[np.ndarray, float, list[str]]] = {}
        for part in parts:
            trimap, trimap_warnings = vitmatte_trimap(rgb, edits_by_part.get(part.id, []))
            alpha = run_vitmatte(runtime, image, trimap)
            mask = alpha >= confidence_threshold
            confidence = float(alpha[mask].mean()) if np.any(mask) else 0.0
            output[part.id] = (mask.astype(bool), confidence, trimap_warnings)
            LOGGER.info(
                "vitmatte part inference done: part=%s confidence=%.4f area=%s trimap_unknown=%s",
                part.id,
                confidence,
                int(mask.sum()),
                int(np.count_nonzero(trimap == 128)),
            )
        if runtime.device != "cpu" and torch.cuda.is_available():
            torch.cuda.synchronize()
        return output
    except Exception as error:  # pragma: no cover - depends on ViTMatte runtime.
        clear_cuda_cache()
        warning = f"ViTMatte inference failed: {error}"
        LOGGER.exception("vitmatte inference failed")
        if fallback_masks_enabled():
            return {part.id: (fallback_semantic_mask(rgb), 0.25, [warning]) for part in parts}
        return {part.id: (np.zeros(rgb.shape[:2], dtype=bool), 0.0, [warning]) for part in parts}


def run_vitmatte(runtime: Sam3Runtime, image: Image.Image, trimap: np.ndarray) -> np.ndarray:
    import torch

    trimap_image = Image.fromarray(trimap.astype(np.uint8), mode="L")
    inputs = runtime.processor(images=image, trimaps=trimap_image, return_tensors="pt")
    target_device = runtime.device if runtime.device != "cpu" and torch.cuda.is_available() else "cpu"
    prepared = {}
    for key, value in inputs.items():
        tensor = value.to(target_device)
        if runtime.half and target_device != "cpu" and tensor.is_floating_point():
            tensor = tensor.half()
        prepared[key] = tensor
    with torch.no_grad():
        outputs = runtime.model(**prepared)
    alpha = outputs.alphas.detach().float().cpu().numpy()[0, 0]
    return np.clip(alpha, 0.0, 1.0)


def vitmatte_trimap(rgb: np.ndarray, edits: list[PartEdit]) -> tuple[np.ndarray, list[str]]:
    height, width = rgb.shape[:2]
    trimap = np.zeros((height, width), dtype=np.uint8)
    warnings: list[str] = []
    bbox = latest_bbox_edit(edits)
    positive_points = [
        (edit.x, edit.y)
        for edit in edits
        if edit.type == "positive_point" and edit.x is not None and edit.y is not None
    ]
    negative_points = [
        (edit.x, edit.y)
        for edit in edits
        if edit.type == "negative_point" and edit.x is not None and edit.y is not None
    ]

    if bbox:
        x1, y1, x2, y2 = clamp_box_xyxy(bbox, width, height)
        if x2 > x1 and y2 > y1:
            expanded = expand_box_xyxy([x1, y1, x2, y2], width, height)
            ex1, ey1, ex2, ey2 = [int(round(value)) for value in expanded]
            trimap[ey1:ey2, ex1:ex2] = 128
            if positive_points:
                for x, y in positive_points:
                    draw_trimap_disk(trimap, x, y, max(3, min(width, height) // 48), 255)
            else:
                cx1 = int(round(x1 + (x2 - x1) * 0.35))
                cy1 = int(round(y1 + (y2 - y1) * 0.35))
                cx2 = int(round(x1 + (x2 - x1) * 0.65))
                cy2 = int(round(y1 + (y2 - y1) * 0.65))
                trimap[max(0, cy1) : min(height, cy2), max(0, cx1) : min(width, cx2)] = 255
        else:
            warnings.append("ViTMatte trimap ignored invalid bbox")
    else:
        silhouette = fallback_semantic_mask(rgb)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        unknown = cv2.dilate(silhouette.astype(np.uint8), kernel, iterations=1).astype(bool)
        foreground = cv2.erode(silhouette.astype(np.uint8), kernel, iterations=1).astype(bool)
        trimap[unknown] = 128
        trimap[foreground] = 255
        warnings.append("ViTMatte used silhouette trimap fallback; bbox/point hints unavailable")

    for x, y in negative_points:
        draw_trimap_disk(trimap, x, y, max(3, min(width, height) // 48), 0)

    if not np.any(trimap == 128):
        warnings.append("ViTMatte trimap has no unknown region")
    if not np.any(trimap == 255):
        warnings.append("ViTMatte trimap has no foreground seed")
    return trimap, warnings


def run_visual_prompt(
    predictor: object, shape: tuple[int, int], edits: list[PartEdit]
) -> tuple[np.ndarray, float] | None:
    if not edits:
        return None
    bbox_edits = [edit for edit in edits if edit.type == "bbox" and edit.box and len(edit.box) == 4]
    if bbox_edits:
        pred_masks, pred_boxes = predictor.inference_features(
            predictor.features,
            shape,
            bboxes=[float(value) for value in bbox_edits[-1].box],
        )
        mask, confidence = mask_from_prediction_tensors(pred_masks, pred_boxes, shape, 0.0)
        if np.any(mask):
            return mask, max(0.35, confidence)
    return None


def yolo_candidates(results: object, shape: tuple[int, int], model: object) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for result in results or []:
        masks_obj = getattr(result, "masks", None)
        data = getattr(masks_obj, "data", None)
        if data is None:
            continue
        masks = data.detach().cpu().numpy() if hasattr(data, "detach") else np.asarray(data)
        confidences = confidences_from_result(result, masks.shape[0])
        boxes = yolo_boxes_from_result(result, masks.shape[0])
        class_ids = yolo_classes_from_result(result, masks.shape[0])
        names = getattr(result, "names", None) or getattr(model, "names", {}) or {}
        for index, mask in enumerate(masks):
            candidate = mask.astype(np.float32) > 0.5
            if candidate.shape != shape:
                candidate = cv2.resize(
                    candidate.astype(np.uint8), (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST
                ).astype(bool)
            area = int(candidate.sum())
            if area <= 0:
                continue
            class_id = class_ids[index] if index < len(class_ids) else -1
            class_name = str(names.get(class_id, class_id)) if isinstance(names, dict) else str(class_id)
            candidates.append(
                {
                    "mask": candidate,
                    "confidence": confidences[index] if index < len(confidences) else 0.8,
                    "box": boxes[index] if index < len(boxes) else box_xyxy_from_mask(candidate),
                    "className": class_name,
                    "area": area,
                }
            )
    return candidates


def yolo_boxes_from_result(result: object, count: int) -> list[list[float]]:
    boxes = getattr(result, "boxes", None)
    xyxy = getattr(boxes, "xyxy", None)
    if xyxy is None:
        return [[] for _ in range(count)]
    values = xyxy.detach().cpu().numpy() if hasattr(xyxy, "detach") else np.asarray(xyxy)
    return [[float(v) for v in row[:4]] for row in values]


def yolo_classes_from_result(result: object, count: int) -> list[int]:
    boxes = getattr(result, "boxes", None)
    cls = getattr(boxes, "cls", None)
    if cls is None:
        return [-1] * count
    values = cls.detach().cpu().numpy() if hasattr(cls, "detach") else np.asarray(cls)
    return [int(value) for value in values]


def select_yolo_mask_for_part(
    part: SemanticPartSpec,
    candidates: list[dict[str, object]],
    edits: list[PartEdit],
    shape: tuple[int, int],
    confidence_threshold: float,
) -> tuple[np.ndarray, float, list[str]]:
    usable = [candidate for candidate in candidates if float(candidate["confidence"]) >= confidence_threshold]
    if not usable:
        return np.zeros(shape, dtype=bool), 0.0, ["YOLO26 returned no segmentation masks"]

    bbox = latest_bbox_edit(edits)
    positive_points = [
        (edit.x, edit.y)
        for edit in edits
        if edit.type == "positive_point" and edit.x is not None and edit.y is not None
    ]
    negative_points = [
        (edit.x, edit.y)
        for edit in edits
        if edit.type == "negative_point" and edit.x is not None and edit.y is not None
    ]
    if bbox:
        scored = [
            (box_iou(candidate["box"], bbox), float(candidate["confidence"]), int(candidate["area"]), candidate)
            for candidate in usable
        ]
        best_score, _, _, best = max(scored, key=lambda item: item[:3])
        if best_score > 0.0:
            return best["mask"], float(best["confidence"]), []

    pointed = [
        candidate for candidate in usable if points_match_mask(candidate["mask"], positive_points, negative_points)
    ]
    if pointed:
        best = max(pointed, key=lambda candidate: (float(candidate["confidence"]), int(candidate["area"])))
        return best["mask"], float(best["confidence"]), []

    tokens = prompt_tokens(f"{part.label} {part.prompt}")
    named = [
        (
            len(tokens & prompt_tokens(str(candidate["className"]))),
            float(candidate["confidence"]),
            int(candidate["area"]),
            candidate,
        )
        for candidate in usable
    ]
    named = [item for item in named if item[0] > 0]
    if named:
        _, _, _, best = max(named, key=lambda item: item[:3])
        return best["mask"], float(best["confidence"]), []

    best = max(usable, key=lambda candidate: (int(candidate["area"]), float(candidate["confidence"])))
    return (
        best["mask"],
        float(best["confidence"]),
        ["YOLO26 used largest mask fallback; prompt/class match unavailable"],
    )


def clear_cuda_cache() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        return


def mask_from_results(results: object, shape: tuple[int, int], confidence_threshold: float) -> tuple[np.ndarray, float]:
    best_mask: np.ndarray | None = None
    best_confidence = 0.0
    best_area = -1
    for result in results or []:
        masks_obj = getattr(result, "masks", None)
        data = getattr(masks_obj, "data", None)
        if data is None:
            continue
        masks = data.detach().cpu().numpy() if hasattr(data, "detach") else np.asarray(data)
        confidences = confidences_from_result(result, masks.shape[0])
        for index, mask in enumerate(masks):
            confidence = confidences[index] if index < len(confidences) else 0.8
            if confidence < confidence_threshold:
                continue
            candidate = mask.astype(np.float32) > 0.5
            area = int(candidate.sum())
            if area > best_area:
                best_mask = candidate
                best_confidence = float(confidence)
                best_area = area
    if best_mask is None:
        return np.zeros(shape, dtype=bool), 0.0
    if best_mask.shape != shape:
        best_mask = cv2.resize(
            best_mask.astype(np.uint8), (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST
        ).astype(bool)
    return best_mask.astype(bool), best_confidence


def mask_from_prediction_tensors(
    pred_masks: object,
    pred_boxes: object,
    shape: tuple[int, int],
    confidence_threshold: float,
    class_index: int | None = None,
) -> tuple[np.ndarray, float]:
    if pred_masks is None:
        return np.zeros(shape, dtype=bool), 0.0
    masks = pred_masks.detach().cpu().numpy() if hasattr(pred_masks, "detach") else np.asarray(pred_masks)
    boxes = pred_boxes.detach().cpu().numpy() if hasattr(pred_boxes, "detach") else np.asarray(pred_boxes)
    best_mask: np.ndarray | None = None
    best_confidence = 0.0
    best_area = -1
    for index, mask in enumerate(masks):
        box = boxes[index] if index < len(boxes) else []
        confidence = float(box[4]) if len(box) >= 5 else 0.8
        detected_class = int(box[5]) if len(box) >= 6 else 0
        if class_index is not None and detected_class != class_index:
            continue
        if confidence < confidence_threshold:
            continue
        candidate = mask.astype(np.float32) > 0.5
        area = int(candidate.sum())
        if area > best_area:
            best_mask = candidate
            best_confidence = confidence
            best_area = area
    if best_mask is None:
        return np.zeros(shape, dtype=bool), 0.0
    if best_mask.shape != shape:
        best_mask = cv2.resize(
            best_mask.astype(np.uint8), (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST
        ).astype(bool)
    return best_mask.astype(bool), best_confidence


def confidences_from_result(result: object, count: int) -> list[float]:
    boxes = getattr(result, "boxes", None)
    conf = getattr(boxes, "conf", None)
    if conf is None:
        return [0.8] * count
    values = conf.detach().cpu().numpy() if hasattr(conf, "detach") else np.asarray(conf)
    return [float(value) for value in values]


def fallback_semantic_mask(rgb: np.ndarray) -> np.ndarray:
    neutral = np.array([128, 128, 128], dtype=np.int16)
    delta = np.abs(rgb.astype(np.int16) - neutral).sum(axis=2)
    mask = delta > 18
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    return cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)


def box_from_mask(mask: np.ndarray) -> list[int] | None:
    ys, xs = np.where(mask)
    if ys.size == 0:
        return None
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    return [x0, y0, x1 - x0, y1 - y0]


def dedupe_warnings(warnings: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for warning in warnings:
        if warning in seen:
            continue
        seen.add(warning)
        output.append(warning)
    return output
