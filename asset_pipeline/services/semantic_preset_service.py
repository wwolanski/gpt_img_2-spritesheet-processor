from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from asset_pipeline.services.config import CONFIG_DIR, DEFAULT_OPTIONS, REPO_ROOT

SEMANTIC_PRESETS_EXAMPLE_FILE = CONFIG_DIR / "semantic_editor_presets.example.json"
SEMANTIC_PRESETS_LEGACY_FILE = CONFIG_DIR / "semantic_editor_presets.json"
RUNTIME_DIR = Path(os.environ.get("ASSET_PIPELINE_RUNTIME_DIR", str(REPO_ROOT / ".runtime"))).expanduser()
SEMANTIC_PRESETS_FILE = Path(
    os.environ.get("ASSET_PIPELINE_PRESETS_FILE", str(RUNTIME_DIR / "semantic_editor_presets.json"))
).expanduser()
SEMANTIC_PRESETS_LOCK_FILE = SEMANTIC_PRESETS_FILE.with_name(f"{SEMANTIC_PRESETS_FILE.name}.lock")
SEMANTIC_PRESETS_VERSION = 2
VALID_INPUT_MODES = {"neutral_matte", "raw_greenscreen", "final_processed"}
VALID_PROJECTION_MODES = {"by_persistence", "source_only", "all_frames"}
VALID_EDIT_TYPES = {"positive_point", "negative_point", "bbox"}
VALID_MOBILITY = {"static", "low", "medium", "high", "accessory"}
VALID_PERSISTENCE = {"always", "occasional"}


def list_semantic_presets() -> dict[str, object]:
    with _preset_lock():
        return {"presets": _load_preset_file()["presets"]}


def save_semantic_preset(name: str, settings: dict[str, object]) -> dict[str, object]:
    normalized_name = normalize_preset_name(name)
    preset = {
        "name": normalized_name,
        "updatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "settings": normalize_preset_settings(settings),
    }
    with _preset_lock():
        payload = _load_preset_file()
        presets = [
            item for item in payload["presets"] if str(item.get("name", "")).casefold() != normalized_name.casefold()
        ]
        presets.append(preset)
        presets.sort(key=lambda item: str(item["name"]).casefold())
        payload["version"] = SEMANTIC_PRESETS_VERSION
        payload["presets"] = presets
        _write_preset_file(payload)
    return {"preset": preset, "presets": presets}


def delete_semantic_preset(name: str) -> dict[str, object]:
    normalized_name = normalize_preset_name(name)
    with _preset_lock():
        payload = _load_preset_file()
        presets = [
            item for item in payload["presets"] if str(item.get("name", "")).casefold() != normalized_name.casefold()
        ]
        if len(presets) == len(payload["presets"]):
            raise FileNotFoundError(f"Unknown semantic preset: {normalized_name}")
        payload["version"] = SEMANTIC_PRESETS_VERSION
        payload["presets"] = presets
        _write_preset_file(payload)
    return {"deleted": normalized_name, "presets": presets}


def normalize_preset_name(name: str) -> str:
    normalized = re.sub(r"\s+", " ", str(name).strip())
    if not normalized:
        raise ValueError("Preset name cannot be empty.")
    if len(normalized) > 80:
        raise ValueError("Preset name is too long (max 80 characters).")
    return normalized


def normalize_preset_settings(settings: dict[str, object]) -> dict[str, object]:
    if not isinstance(settings, dict):
        raise ValueError("Semantic preset payload must be an object.")
    return {
        "semanticInputMode": _string_choice(settings.get("semanticInputMode"), VALID_INPUT_MODES, "neutral_matte"),
        "semanticGroundingMinConfidence": _float_value(
            settings.get("semanticGroundingMinConfidence"),
            float(DEFAULT_OPTIONS.get("semanticGroundingMinConfidence", 0.35)),
        ),
        "semanticGroundingAlphaCutoff": _int_value(
            settings.get("semanticGroundingAlphaCutoff"), int(DEFAULT_OPTIONS.get("semanticGroundingAlphaCutoff", 10))
        ),
        "semanticGroundingDilationRadius": _int_value(
            settings.get("semanticGroundingDilationRadius"),
            int(DEFAULT_OPTIONS.get("semanticGroundingDilationRadius", 2)),
        ),
        "semanticGroundingAllowFrameReassign": _bool_value(
            settings.get("semanticGroundingAllowFrameReassign"),
            bool(DEFAULT_OPTIONS.get("semanticGroundingAllowFrameReassign", True)),
        ),
        "semanticGroundingFrameMinScore": _float_value(
            settings.get("semanticGroundingFrameMinScore"),
            float(DEFAULT_OPTIONS.get("semanticGroundingFrameMinScore", 0.08)),
        ),
        "semanticGroundingProjectionMode": _string_choice(
            settings.get("semanticGroundingProjectionMode"),
            VALID_PROJECTION_MODES,
            str(DEFAULT_OPTIONS.get("semanticGroundingProjectionMode", "by_persistence")),
        ),
        "semanticGroundingExpandRatio": _float_value(
            settings.get("semanticGroundingExpandRatio"),
            float(DEFAULT_OPTIONS.get("semanticGroundingExpandRatio", 0.08)),
        ),
        "semanticGroundingExpandMinPx": _float_value(
            settings.get("semanticGroundingExpandMinPx"), float(DEFAULT_OPTIONS.get("semanticGroundingExpandMinPx", 2))
        ),
        "semanticGroundingEmitBbox": _bool_value(
            settings.get("semanticGroundingEmitBbox"), bool(DEFAULT_OPTIONS.get("semanticGroundingEmitBbox", True))
        ),
        "semanticGroundingEmitPositivePoint": _bool_value(
            settings.get("semanticGroundingEmitPositivePoint"),
            bool(DEFAULT_OPTIONS.get("semanticGroundingEmitPositivePoint", True)),
        ),
        "semanticMaskModel": str(
            settings.get("semanticMaskModel", DEFAULT_OPTIONS.get("semanticMaskModel", "sam3")) or "sam3"
        ),
        "semanticEditorParts": normalize_editor_parts(settings.get("semanticEditorParts", [])),
    }


def normalize_editor_parts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [part for item in value if (part := normalize_editor_part(item)) is not None]


def normalize_editor_part(item: object) -> dict[str, object] | None:
    if not isinstance(item, dict):
        return None
    part_id = normalize_part_id(item.get("id", item.get("label", "")))
    label = str(item.get("label", part_id)).strip() or part_id
    prompt = str(item.get("prompt", label)).strip() or label
    mobility = _string_choice(item.get("mobility"), VALID_MOBILITY, "medium")
    persistence = _string_choice(item.get("persistence"), VALID_PERSISTENCE, "always")
    if not part_id:
        return None
    edits = [
        edit for raw_edit in item.get("edits", []) if (edit := normalize_editor_edit(raw_edit, part_id)) is not None
    ]
    part = {
        "id": part_id,
        "label": label,
        "prompt": prompt,
        "mobility": mobility,
        "persistence": persistence,
        "edits": edits,
    }
    stabilize_settings = normalize_stabilize_settings(item.get("stabilizeSettings", item.get("stabilize", {})))
    if stabilize_settings:
        part["stabilizeSettings"] = stabilize_settings
    color = item.get("color")
    if isinstance(color, str) and color.strip():
        part["color"] = color.strip()
    return part


def normalize_stabilize_settings(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    settings: dict[str, object] = {}
    if "enabled" in value:
        settings["enabled"] = _bool_value(value.get("enabled"), True)
    if "repairEnabled" in value:
        settings["repairEnabled"] = _bool_value(value.get("repairEnabled"), True)
    if "repairSearchScale" in value:
        settings["repairSearchScale"] = min(3.0, max(0.1, _float_value(value.get("repairSearchScale"), 1.0)))
    if "patchLockStrength" in value:
        settings["patchLockStrength"] = min(1.5, max(0.0, _float_value(value.get("patchLockStrength"), 1.0)))
    if "medianStrength" in value:
        settings["medianStrength"] = min(1.5, max(0.0, _float_value(value.get("medianStrength"), 1.0)))
    return settings


def normalize_editor_edit(item: object, part_id: str) -> dict[str, object] | None:
    if not isinstance(item, dict):
        return None
    edit_type = item.get("type")
    if edit_type not in VALID_EDIT_TYPES:
        return None
    try:
        frame = int(item.get("frame", 0))
    except (TypeError, ValueError):
        return None
    edit: dict[str, object] = {"frame": frame, "partId": part_id, "type": edit_type}
    if edit_type == "bbox":
        raw_box = item.get("box")
        if not (isinstance(raw_box, list) and len(raw_box) == 4):
            raw_box = [item.get("x0"), item.get("y0"), item.get("x1"), item.get("y1")]
        try:
            edit["box"] = [float(value) for value in raw_box]
        except (TypeError, ValueError):
            return None
    else:
        try:
            edit["x"] = float(item.get("x"))
            edit["y"] = float(item.get("y"))
        except (TypeError, ValueError):
            return None
    space = normalize_edit_space(item.get("space"))
    if space:
        edit["space"] = space
    return edit


def normalize_edit_space(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    try:
        frame_width = int(value.get("frameWidth", 0))
        frame_height = int(value.get("frameHeight", 0))
    except (TypeError, ValueError):
        return None
    if frame_width <= 0 or frame_height <= 0:
        return None
    space: dict[str, object] = {
        "coordinateSpace": str(
            value.get("coordinateSpace", "semantic_input_pre_upscale") or "semantic_input_pre_upscale"
        ),
        "frameWidth": frame_width,
        "frameHeight": frame_height,
    }
    source_width = _optional_int(value.get("sourceWidth"))
    source_height = _optional_int(value.get("sourceHeight"))
    offset_x = _optional_int(value.get("offsetX"), allow_zero=True)
    offset_y = _optional_int(value.get("offsetY"), allow_zero=True)
    preview_id = value.get("previewId")
    if source_width is not None:
        space["sourceWidth"] = source_width
    if source_height is not None:
        space["sourceHeight"] = source_height
    if offset_x is not None:
        space["offsetX"] = offset_x
    if offset_y is not None:
        space["offsetY"] = offset_y
    if isinstance(preview_id, str) and preview_id.strip():
        space["previewId"] = preview_id.strip()
    return space


def normalize_part_id(value: object) -> str:
    text = re.sub(r"[^a-z0-9_]+", "_", str(value).strip().lower())
    return text.strip("_")


def _load_preset_file() -> dict[str, object]:
    source_file = SEMANTIC_PRESETS_FILE
    migrate_legacy = False
    if not source_file.exists() and SEMANTIC_PRESETS_LEGACY_FILE.exists():
        source_file = SEMANTIC_PRESETS_LEGACY_FILE
        migrate_legacy = True
    if not source_file.exists():
        return {"version": SEMANTIC_PRESETS_VERSION, "presets": []}
    try:
        raw = json.loads(source_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid semantic preset file: {source_file}") from error
    presets = raw.get("presets", []) if isinstance(raw, dict) else []
    version = int(raw.get("version", 1)) if isinstance(raw, dict) else 1
    if version > SEMANTIC_PRESETS_VERSION:
        raise ValueError(f"Unsupported semantic preset version: {version}")
    payload = {
        "version": SEMANTIC_PRESETS_VERSION,
        "presets": [preset for item in presets if (preset := _normalize_loaded_preset(item)) is not None],
    }
    if migrate_legacy or version != SEMANTIC_PRESETS_VERSION:
        _write_preset_file(payload)
    return payload


def _normalize_loaded_preset(item: object) -> dict[str, object] | None:
    if not isinstance(item, dict):
        return None
    try:
        name = normalize_preset_name(str(item.get("name", "")))
    except ValueError:
        return None
    updated_at = str(item.get("updatedAt", "")).strip() or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    settings = normalize_preset_settings(item.get("settings", {}))
    return {"name": name, "updatedAt": updated_at, "settings": settings}


def _write_preset_file(payload: dict[str, object]) -> None:
    SEMANTIC_PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": SEMANTIC_PRESETS_VERSION, "presets": payload.get("presets", [])}
    temporary_path: str | None = None
    try:
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=f".{SEMANTIC_PRESETS_FILE.name}.",
            suffix=".tmp",
            dir=SEMANTIC_PRESETS_FILE.parent,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, SEMANTIC_PRESETS_FILE)
        temporary_path = None
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


@contextmanager
def _preset_lock() -> Iterator[None]:
    SEMANTIC_PRESETS_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SEMANTIC_PRESETS_LOCK_FILE.open("a+", encoding="utf-8") as lock_file:
        try:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except ImportError:  # pragma: no cover - Windows fallback
            pass
        try:
            yield
        finally:
            try:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except ImportError:  # pragma: no cover - Windows fallback
                pass


def _string_choice(value: object, allowed: set[str], default: str) -> str:
    text = str(value).strip()
    return text if text in allowed else default


def _float_value(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _int_value(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _bool_value(value: object, default: bool) -> bool:
    return bool(value) if isinstance(value, bool) else default


def _optional_int(value: object, allow_zero: bool = False) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if allow_zero:
        return parsed if parsed >= 0 else None
    return parsed if parsed > 0 else None
