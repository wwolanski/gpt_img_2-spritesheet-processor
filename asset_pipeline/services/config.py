from __future__ import annotations

import json
import math
import os
from pathlib import Path

from asset_pipeline.services.errors import ConfigValidationError
from asset_pipeline.services.models import PipelineProfile, PipelineStage, StageDefinition

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET_PIPELINE_DIR = REPO_ROOT / "asset_pipeline"
CONFIG_DIR = ASSET_PIPELINE_DIR / "config"
PIPELINES_CONFIG_DIR = CONFIG_DIR / "pipelines"
SOURCES_DIR = ASSET_PIPELINE_DIR / "sources"
WORKBENCH_DIR = ASSET_PIPELINE_DIR / "workbench"
# Preview generation defaults to RAM (`ASSET_PIPELINE_PREVIEW_STORAGE=memory`)
# and does not touch this directory. For AI/VSCode debugging, run CLI with
# `--preview-storage disk`; outputs land here:
# `asset_pipeline/workbench/previews/<preview-id>/{processed,sheet,alpha,metadata}.`
PREVIEWS_DIR = Path(os.environ.get("ASSET_PIPELINE_PREVIEWS_DIR", WORKBENCH_DIR / "previews"))
EXPORTS_DIR = WORKBENCH_DIR / "exports"
PUBLIC_ASSETS_DIR = REPO_ROOT / "client" / "public" / "assets"

DEFAULTS_CONFIG = json.loads((CONFIG_DIR / "defaults.json").read_text(encoding="utf-8"))
DEFAULT_WORKERS = int(DEFAULTS_CONFIG["defaultWorkers"])
DEFAULT_OPTIONS: dict[str, object] = dict(DEFAULTS_CONFIG["defaultOptions"])
PROFILE_PRESETS: dict[str, dict[str, object]] = {
    str(key): dict(value) for key, value in DEFAULTS_CONFIG["profilePresets"].items()
}

OPTION_RANGES: dict[str, tuple[float, float]] = {
    "transparentThreshold": (0, 255),
    "opaqueThreshold": (0, 255),
    "greenHueCenter": (0, 360),
    "greenHueRange": (0, 180),
    "greenSaturationMin": (0, 255),
    "greenValueMin": (0, 255),
    "greenDominanceSoft": (0, 255),
    "greenDominanceHard": (0, 255),
    "edgeSoftness": (0, 20),
    "edgeBlurSigma": (0, 20),
    "despillStrength": (0, 2.4),
    "despillAlphaStrength": (0, 2.4),
    "neutralizeStrength": (0, 2.4),
    "edgeDarken": (0, 1),
    "outlineWidth": (0, 32),
    "outlineOpacity": (0, 1),
    "outlineBlur": (0, 20),
    "alphaCleanupMinArea": (0, 1_000_000),
    "alphaCleanupCloseSize": (0, 64),
    "cropPadding": (0, 512),
    "framePadding": (0, 512),
    "minFrameArea": (1, 1_000_000),
    "alphaCutoff": (0, 255),
    "flowDeflickerStrength": (0, 1),
    "flowDeflickerRadius": (0, 32),
    "flowColorTolerance": (0, 255),
    "flowAlphaTolerance": (0, 255),
    "flowConsistencyTolerance": (0, 32),
    "flowMaxDisplacement": (0, 512),
    "flowConfidenceFloor": (0, 1),
    "temporalDeflickerStrength": (0, 1),
    "temporalStaticCoverage": (0, 1),
    "temporalColorTolerance": (0, 255),
    "temporalAlphaTolerance": (0, 255),
    "sheetExtrudePixels": (0, 64),
    "semanticGroundingMinConfidence": (0, 1),
    "semanticGroundingAlphaCutoff": (0, 255),
    "semanticGroundingDilationRadius": (0, 64),
    "semanticGroundingFrameMinScore": (0, 1),
    "semanticGroundingExpandRatio": (0, 1),
    "semanticGroundingExpandMinPx": (0, 512),
    "partRepairSearchScale": (0.1, 3),
    "partPatchLockStrength": (0, 1.5),
    "partMedianStrength": (0, 1.5),
}

OPTION_CHOICES: dict[str, set[str]] = {
    "profile": {"auto", "outline", "thick-outline", "pixelart"},
    "despillAlphaMode": {"preserve", "spill-transparent"},
    "neutralizeEdges": {"auto", "gray", "black"},
    "upscaleMode": {"none", "nearest-2x", "nearest-4x", "aura-sr"},
    "semanticInputMode": {"neutral_matte", "raw_greenscreen", "final_processed"},
    "semanticGroundingProjectionMode": {"by_persistence", "source_only", "all_frames"},
}


def validate_option_values(values: object, location: str, errors: list[str]) -> None:
    if not isinstance(values, dict):
        errors.append(f"{location}: options must be an object")
        return
    for key, value in values.items():
        option_name = str(key)
        if option_name in OPTION_RANGES:
            try:
                numeric_value = float(value) if not isinstance(value, bool) else float("nan")
            except (TypeError, ValueError, OverflowError):
                numeric_value = float("nan")
            if not isinstance(value, (int, float)) or not math.isfinite(numeric_value):
                errors.append(f"{location}.{option_name}: expected a finite number")
                continue
            minimum, maximum = OPTION_RANGES[option_name]
            if not minimum <= numeric_value <= maximum:
                errors.append(f"{location}.{option_name}: must be between {minimum} and {maximum}")
        choices = OPTION_CHOICES.get(option_name)
        if choices is not None and (not isinstance(value, str) or value not in choices):
            errors.append(f"{location}.{option_name}: unsupported value {value!r}")
    transparent = values.get("transparentThreshold")
    opaque = values.get("opaqueThreshold")
    if isinstance(transparent, (int, float)) and not isinstance(transparent, bool):
        if isinstance(opaque, (int, float)) and not isinstance(opaque, bool) and opaque < transparent:
            errors.append(f"{location}: opaqueThreshold must be greater than or equal to transparentThreshold")


def load_stage_registry() -> dict[str, StageDefinition]:
    entries = json.loads((CONFIG_DIR / "stage_registry.json").read_text(encoding="utf-8"))
    return {
        str(entry["id"]): StageDefinition(
            id=str(entry["id"]),
            label=str(entry["label"]),
            description=str(entry["description"]),
            configurable=bool(entry["configurable"]),
        )
        for entry in entries
    }


STAGE_REGISTRY = load_stage_registry()
STAGE_ORDER = tuple(STAGE_REGISTRY.keys())


def load_pipeline_profile(pipeline_id: str) -> PipelineProfile:
    data = json.loads((PIPELINES_CONFIG_DIR / f"{pipeline_id}.json").read_text(encoding="utf-8"))
    stages = tuple(PipelineStage(id=str(stage["id"]), included=bool(stage["included"])) for stage in data["stages"])
    unknown_stages = [stage.id for stage in stages if stage.id not in STAGE_REGISTRY]
    if unknown_stages:
        raise ValueError(f"Unknown stages in {pipeline_id}: {unknown_stages}")
    configured_order = [stage.id for stage in stages]
    expected_order = [stage_id for stage_id in STAGE_ORDER if stage_id in configured_order]
    if configured_order != expected_order:
        raise ValueError(f"Invalid stage order in {pipeline_id}: {configured_order}")
    return PipelineProfile(
        id=str(data["id"]),
        label=str(data["label"]),
        description=str(data["description"]),
        profile_hint=str(data["profileHint"]),
        stages=stages,
        option_overrides=dict(data.get("optionOverrides", {})),
        optional=data.get("optional"),
    )


PIPELINE_PROFILES: dict[str, PipelineProfile] = {
    pipeline_id: load_pipeline_profile(pipeline_id) for pipeline_id in DEFAULTS_CONFIG["pipelineOrder"]
}


def default_stage_map(pipeline: PipelineProfile) -> dict[str, bool]:
    return {stage.id: stage.included for stage in pipeline.stages}


def resolved_stage_map(pipeline: PipelineProfile, raw_options: dict[str, object] | None) -> dict[str, bool]:
    stages = default_stage_map(pipeline)
    overrides = (raw_options or {}).get("pipelineStages", {})
    if not isinstance(overrides, dict):
        return stages
    for stage_id, included in overrides.items():
        definition = STAGE_REGISTRY.get(str(stage_id))
        if definition and definition.configurable:
            stages[str(stage_id)] = bool(included)
    return stages


def resolved_stage_ids(pipeline: PipelineProfile, raw_options: dict[str, object] | None) -> tuple[str, ...]:
    stages = resolved_stage_map(pipeline, raw_options)
    return tuple(stage_id for stage_id in STAGE_ORDER if stages.get(stage_id))


def validate_config(config_dir: Path = CONFIG_DIR) -> list[str]:
    """Validate every tracked JSON configuration file without mutating runtime state."""

    errors: list[str] = []

    def read_json(relative_path: str) -> object | None:
        path = config_dir / relative_path
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            errors.append(f"{relative_path}: file does not exist")
        except json.JSONDecodeError as error:
            errors.append(f"{relative_path}: invalid JSON at line {error.lineno}, column {error.colno}")
        except OSError as error:
            errors.append(f"{relative_path}: cannot read file ({error})")
        return None

    defaults = read_json("defaults.json")
    registry = read_json("stage_registry.json")
    example_presets = read_json("semantic_editor_presets.example.json")

    registry_ids: list[str] = []
    if not isinstance(registry, list) or not registry:
        errors.append("stage_registry.json: expected a non-empty array")
    else:
        for index, entry in enumerate(registry):
            if not isinstance(entry, dict):
                errors.append(f"stage_registry.json: entry {index} must be an object")
                continue
            stage_id = entry.get("id")
            if not isinstance(stage_id, str) or not stage_id:
                errors.append(f"stage_registry.json: entry {index} has an invalid id")
                continue
            registry_ids.append(stage_id)
            for required in ("label", "description", "configurable"):
                if required not in entry:
                    errors.append(f"stage_registry.json: {stage_id} is missing '{required}'")
            if not isinstance(entry.get("configurable"), bool):
                errors.append(f"stage_registry.json: {stage_id}.configurable must be boolean")
        duplicates = sorted({stage_id for stage_id in registry_ids if registry_ids.count(stage_id) > 1})
        if duplicates:
            errors.append(f"stage_registry.json: duplicate stage ids: {duplicates}")

    pipeline_order: list[str] = []
    if not isinstance(defaults, dict):
        errors.append("defaults.json: expected an object")
    else:
        default_workers = defaults.get("defaultWorkers")
        if not isinstance(default_workers, int) or isinstance(default_workers, bool) or default_workers < 1:
            errors.append("defaults.json: defaultWorkers must be a positive integer")
        if not isinstance(defaults.get("defaultOptions"), dict):
            errors.append("defaults.json: defaultOptions must be an object")
        else:
            validate_option_values(defaults["defaultOptions"], "defaults.json.defaultOptions", errors)
        if not isinstance(defaults.get("profilePresets"), dict):
            errors.append("defaults.json: profilePresets must be an object")
        else:
            for profile_name, profile_options in defaults["profilePresets"].items():
                validate_option_values(profile_options, f"defaults.json.profilePresets.{profile_name}", errors)
        raw_pipeline_order = defaults.get("pipelineOrder")
        if not isinstance(raw_pipeline_order, list) or not raw_pipeline_order:
            errors.append("defaults.json: pipelineOrder must be a non-empty array")
        else:
            pipeline_order = [str(value) for value in raw_pipeline_order]
            if any(not isinstance(value, str) or not value for value in raw_pipeline_order):
                errors.append("defaults.json: pipelineOrder must contain non-empty strings")
            if len(set(pipeline_order)) != len(pipeline_order):
                errors.append("defaults.json: pipelineOrder contains duplicates")

    pipeline_dir = config_dir / "pipelines"
    configured_files = {path.stem for path in pipeline_dir.glob("*.json")}
    expected_files = set(pipeline_order)
    for pipeline_id in sorted(expected_files - configured_files):
        errors.append(f"pipelines/{pipeline_id}.json: file is missing from pipelineOrder")
    for pipeline_id in sorted(configured_files - expected_files):
        errors.append(f"pipelines/{pipeline_id}.json: file is not listed in defaults.pipelineOrder")

    for pipeline_id in sorted(configured_files | expected_files):
        relative_path = f"pipelines/{pipeline_id}.json"
        data = read_json(relative_path)
        if not isinstance(data, dict):
            errors.append(f"{relative_path}: expected an object")
            continue
        if data.get("id") != pipeline_id:
            errors.append(f"{relative_path}: id must match filename '{pipeline_id}'")
        for required in ("label", "description", "profileHint", "stages"):
            if required not in data:
                errors.append(f"{relative_path}: missing '{required}'")
        if not isinstance(data.get("stages"), list):
            errors.append(f"{relative_path}: stages must be an array")
            continue
        stage_ids: list[str] = []
        for index, stage in enumerate(data["stages"]):
            if not isinstance(stage, dict):
                errors.append(f"{relative_path}: stage {index} must be an object")
                continue
            stage_id = stage.get("id")
            if not isinstance(stage_id, str) or not stage_id:
                errors.append(f"{relative_path}: stage {index} has an invalid id")
                continue
            stage_ids.append(stage_id)
            if not isinstance(stage.get("included"), bool):
                errors.append(f"{relative_path}: {stage_id}.included must be boolean")
        if len(set(stage_ids)) != len(stage_ids):
            errors.append(f"{relative_path}: stages contain duplicate ids")
        missing = [stage_id for stage_id in registry_ids if stage_id not in stage_ids]
        unknown = [stage_id for stage_id in stage_ids if stage_id not in registry_ids]
        if missing:
            errors.append(f"{relative_path}: missing stages {missing}")
        if unknown:
            errors.append(f"{relative_path}: unknown stages {unknown}")
        expected_order = [stage_id for stage_id in registry_ids if stage_id in stage_ids]
        if stage_ids != expected_order:
            errors.append(f"{relative_path}: stages are not in stage_registry order")
        if not isinstance(data.get("optionOverrides", {}), dict):
            errors.append(f"{relative_path}: optionOverrides must be an object")
        else:
            validate_option_values(data["optionOverrides"], f"{relative_path}.optionOverrides", errors)
        optional = data.get("optional")
        if optional is not None and not isinstance(optional, str):
            errors.append(f"{relative_path}: optional must be a string or null")

    if not isinstance(example_presets, dict):
        errors.append("semantic_editor_presets.example.json: expected an object")
    else:
        if example_presets.get("version") != 2:
            errors.append("semantic_editor_presets.example.json: version must be 2")
        presets = example_presets.get("presets")
        if not isinstance(presets, list):
            errors.append("semantic_editor_presets.example.json: presets must be an array")
        else:
            for index, preset in enumerate(presets):
                if not isinstance(preset, dict):
                    errors.append(f"semantic_editor_presets.example.json: preset {index} must be an object")
                    continue
                if not isinstance(preset.get("name"), str) or not preset.get("name"):
                    errors.append(f"semantic_editor_presets.example.json: preset {index} has an invalid name")
                if not isinstance(preset.get("settings"), dict):
                    errors.append(f"semantic_editor_presets.example.json: preset {index}.settings must be an object")

    return errors


def validate_config_or_raise(config_dir: Path = CONFIG_DIR) -> None:
    errors = validate_config(config_dir)
    if errors:
        raise ConfigValidationError(
            "Configuration validation failed.",
            details={"errors": errors},
        )
