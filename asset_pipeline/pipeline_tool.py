#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from asset_pipeline.services.config import (
    DEFAULT_OPTIONS,
    DEFAULT_WORKERS,
    PIPELINE_PROFILES,
    PROFILE_PRESETS,
    STAGE_REGISTRY,
    validate_option_values,
    validate_config,
    validate_config_or_raise,
)
from asset_pipeline.services.capabilities import aura_sr_installed, optional_service_capabilities
from asset_pipeline.services.contracts import JsonObject
from asset_pipeline.services.errors import ConfigValidationError, ValidationError, error_payload
from asset_pipeline.services.rembg_service import rembg_installed
from asset_pipeline.services.request_validation import (
    MAX_REQUEST_BODY_BYTES,
    validate_pipeline_ids,
    validate_payload,
    validate_source_name,
    validate_source_names,
    validate_workers,
)
from asset_pipeline.services.runner_service import compare_matrix, compare_pipelines, process_source
from asset_pipeline.services.semantic_preset_service import (
    delete_semantic_preset,
    list_semantic_presets,
    save_semantic_preset,
)
from asset_pipeline.services.storage_service import export_preview, list_sources, paths_payload

LOGGER = logging.getLogger("asset_pipeline.cli")


def emit_json(payload: JsonObject) -> None:
    sys.stdout.write(json.dumps(payload, indent=2))
    sys.stdout.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Modular sprite asset pipeline workbench.",
        epilog="Debug tip: add --preview-storage disk to process/compare/compare-matrix when an agent needs PNG outputs on disk.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("describe", help="Print pipeline capabilities and defaults.")
    subparsers.add_parser("validate-config", help="Validate all tracked pipeline JSON files.")
    subparsers.add_parser("list-sources", help="List available source images.")
    subparsers.add_parser("list-semantic-presets", help="List saved semantic editor presets.")

    process_parser = subparsers.add_parser("process", help="Process one source into preview workspace.")
    process_parser.add_argument("--source", required=True, help="Source filename relative to asset_pipeline/sources.")
    process_parser.add_argument("--preview-id", required=True, help="Preview directory id.")
    process_parser.add_argument(
        "--preview-storage",
        choices=("memory", "disk"),
        default=None,
        help="memory returns inline PNGs; disk writes asset_pipeline/workbench/previews for debugging.",
    )

    compare_parser = subparsers.add_parser("compare", help="Process many pipeline profiles concurrently.")
    compare_parser.add_argument("--source", required=True, help="Source filename relative to asset_pipeline/sources.")
    compare_parser.add_argument("--batch-id", required=True, help="Stable id prefix for preview directories.")
    compare_parser.add_argument(
        "--workers", type=validate_workers, default=DEFAULT_WORKERS, help="Max process workers."
    )
    compare_parser.add_argument(
        "--preview-storage",
        choices=("memory", "disk"),
        default=None,
        help="Use disk when another agent needs to inspect generated PNG files.",
    )

    compare_matrix_parser = subparsers.add_parser(
        "compare-matrix", help="Process many sources and pipeline profiles concurrently."
    )
    compare_matrix_parser.add_argument(
        "--source", action="append", dest="sources", help="Source filename. Repeatable. Defaults to every source."
    )
    compare_matrix_parser.add_argument("--batch-id", required=True, help="Stable id prefix for preview directories.")
    compare_matrix_parser.add_argument(
        "--workers", type=validate_workers, default=DEFAULT_WORKERS, help="Max process workers."
    )
    compare_matrix_parser.add_argument(
        "--preview-storage",
        choices=("memory", "disk"),
        default=None,
        help="Use disk when another agent needs to inspect generated PNG files.",
    )

    export_parser = subparsers.add_parser("export", help="Export one preview into client/public/assets.")
    export_parser.add_argument("--preview-id", required=True, help="Preview directory id.")
    export_parser.add_argument(
        "--target-name", required=True, help="Export folder name under client/public/assets/generated."
    )
    export_parser.add_argument(
        "--overwrite", action="store_true", help="Replace an existing export with the same target name."
    )

    save_semantic_preset_parser = subparsers.add_parser("save-semantic-preset", help="Save one semantic editor preset.")
    save_semantic_preset_parser.add_argument("--name", required=True, help="Preset name.")

    delete_semantic_preset_parser = subparsers.add_parser(
        "delete-semantic-preset", help="Delete one semantic editor preset."
    )
    delete_semantic_preset_parser.add_argument("--name", required=True, help="Preset name.")

    return parser.parse_args()


def apply_preview_storage_arg(args: argparse.Namespace) -> None:
    preview_storage = getattr(args, "preview_storage", None)
    if preview_storage:
        os.environ["ASSET_PIPELINE_PREVIEW_STORAGE"] = preview_storage


def load_payload_from_stdin() -> JsonObject:
    raw = sys.stdin.buffer.read(MAX_REQUEST_BODY_BYTES + 1)
    if len(raw) > MAX_REQUEST_BODY_BYTES:
        raise ValidationError(f"request body exceeds {MAX_REQUEST_BODY_BYTES} bytes")
    try:
        text = raw.decode("utf-8").strip()
        if not text:
            return {}
        return validate_payload(json.loads(text))
    except UnicodeDecodeError as error:
        raise ValidationError("request body must be UTF-8 JSON") from error
    except json.JSONDecodeError as error:
        raise ValidationError("request body must contain valid JSON") from error


def options_from_payload(payload: JsonObject) -> dict[str, object]:
    options = payload.get("options", {})
    if not isinstance(options, dict):
        return {}
    errors: list[str] = []
    validate_option_values(options, "options", errors)
    pipeline_options = options.get("pipelineOptions")
    if isinstance(pipeline_options, dict):
        for pipeline_id, pipeline_values in pipeline_options.items():
            validate_option_values(pipeline_values, f"options.pipelineOptions.{pipeline_id}", errors)
    if errors:
        raise ValidationError("Invalid pipeline options.", details={"errors": errors})
    return dict(options)


def pipeline_from_payload(payload: JsonObject) -> str | None:
    pipeline_id = payload.get("pipelineId")
    if pipeline_id is None:
        return None
    if not isinstance(pipeline_id, str) or not pipeline_id:
        raise ValidationError("pipelineId must be a non-empty string")
    return pipeline_id


def pipeline_ids_from_payload(payload: JsonObject) -> list[str] | None:
    pipeline_ids = validate_pipeline_ids(payload.get("pipelineIds"))
    if pipeline_ids:
        known_ids = set(PIPELINE_PROFILES)
        unknown_ids = sorted(set(pipeline_ids) - known_ids)
        if unknown_ids:
            raise ValidationError("Unknown pipeline ids.", details={"pipelineIds": unknown_ids})
    return pipeline_ids


def describe() -> JsonObject:
    rembg_available = rembg_installed()
    pipeline_entries = []
    for pipeline in PIPELINE_PROFILES.values():
        enabled = not pipeline.optional or (pipeline.optional == "rembg" and rembg_available)
        pipeline_entries.append(
            {
                "id": pipeline.id,
                "enabled": enabled,
                "label": pipeline.label,
                "description": pipeline.description,
                "profile_hint": pipeline.profile_hint,
                "stages": [asdict(stage) for stage in pipeline.stages],
                "optionOverrides": pipeline.option_overrides,
                "optional": pipeline.optional,
            }
        )
    return {
        "defaults": DEFAULT_OPTIONS,
        "profiles": ["auto", *PROFILE_PRESETS.keys()],
        "profilePresets": PROFILE_PRESETS,
        "stageRegistry": [asdict(stage) for stage in STAGE_REGISTRY.values()],
        "pipelines": pipeline_entries,
        "capabilities": {
            "rembg": rembg_available,
            "auraSr": aura_sr_installed(),
            **optional_service_capabilities(),
            "workers": DEFAULT_WORKERS,
            "semanticMaskModels": ["sam3", "yolo26", "vitmatte", "inspirinet"],
        },
        "paths": paths_payload(),
    }


def validate_config_command() -> JsonObject:
    errors = validate_config()
    if errors:
        raise ConfigValidationError(
            "Configuration validation failed.",
            details={"errors": errors},
        )
    return {
        "ok": True,
        "valid": True,
        "errors": [],
        "checked": [
            "defaults.json",
            "stage_registry.json",
            "semantic_editor_presets.example.json",
            "pipelines/*.json",
        ],
    }


def configure_logging() -> None:
    level_name = os.environ.get("ASSET_PIPELINE_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )


def main() -> int:
    configure_logging()
    args = parse_args()
    apply_preview_storage_arg(args)
    try:
        if args.command == "validate-config":
            emit_json(validate_config_command())
            return 0
        validate_config_or_raise()
        if args.command == "describe":
            emit_json(describe())
            return 0
        if args.command == "list-sources":
            emit_json(list_sources())
            return 0
        if args.command == "list-semantic-presets":
            emit_json(list_semantic_presets())
            return 0
        if args.command == "process":
            payload = load_payload_from_stdin()
            emit_json(
                process_source(
                    validate_source_name(args.source),
                    args.preview_id,
                    options_from_payload(payload),
                    pipeline_from_payload(payload),
                )
            )
            return 0
        if args.command == "compare":
            payload = load_payload_from_stdin()
            emit_json(
                compare_pipelines(
                    validate_source_name(args.source),
                    args.batch_id,
                    options_from_payload(payload),
                    pipeline_ids_from_payload(payload),
                    args.workers,
                )
            )
            return 0
        if args.command == "compare-matrix":
            payload = load_payload_from_stdin()
            sources = args.sources or [source["name"] for source in list_sources()["sources"]]
            emit_json(
                compare_matrix(
                    validate_source_names(sources),
                    args.batch_id,
                    options_from_payload(payload),
                    pipeline_ids_from_payload(payload),
                    args.workers,
                )
            )
            return 0
        if args.command == "export":
            emit_json(export_preview(args.preview_id, args.target_name, args.overwrite))
            return 0
        if args.command == "save-semantic-preset":
            payload = load_payload_from_stdin()
            emit_json(save_semantic_preset(args.name, payload))
            return 0
        if args.command == "delete-semantic-preset":
            emit_json(delete_semantic_preset(args.name))
            return 0
    except ConfigValidationError as error:
        LOGGER.error("pipeline configuration is invalid: %s", error.message)
        emit_json(error.payload())
        return 1
    except Exception as error:  # pragma: no cover
        status_code, payload = error_payload(error)
        if status_code >= 500:
            LOGGER.exception("pipeline command failed unexpectedly")
        else:
            LOGGER.warning("pipeline command rejected: %s", error)
        emit_json(payload)
        return 1
    raise RuntimeError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
