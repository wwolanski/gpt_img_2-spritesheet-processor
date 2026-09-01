from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from PIL import Image

from asset_pipeline.services.config import EXPORTS_DIR, PREVIEWS_DIR, PUBLIC_ASSETS_DIR, REPO_ROOT, SOURCES_DIR
from asset_pipeline.services.errors import AssetPipelineError
from asset_pipeline.services.workspace_service import preview_dir_for


def ensure_workspace() -> None:
    if os.environ.get("ASSET_PIPELINE_PREVIEW_STORAGE", "memory") != "memory":
        PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def safe_source_path(source_name: str) -> Path:
    candidate = (SOURCES_DIR / source_name).resolve()
    if SOURCES_DIR.resolve() not in candidate.parents or not candidate.is_file():
        raise FileNotFoundError(f"Unknown source asset: {source_name}")
    return candidate


def list_sources() -> dict[str, object]:
    sources = []
    for path in sorted(SOURCES_DIR.glob("*")):
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        with Image.open(path) as image:
            width, height = image.size
        sources.append({"name": path.name, "width": width, "height": height, "bytes": path.stat().st_size})
    return {"sources": sources}


def export_preview(preview_id: str, target_name: str, overwrite: bool = False) -> dict[str, object]:
    preview_dir = preview_dir_for(preview_id)
    if not preview_dir.is_dir():
        raise FileNotFoundError(f"Unknown preview id: {preview_id}")

    metadata = json.loads((preview_dir / "metadata.json").read_text(encoding="utf-8"))
    safe_target = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-" for character in target_name
    ).strip("-")
    if not safe_target:
        raise ValueError("Invalid export target name.")

    export_dir = EXPORTS_DIR / safe_target
    public_dir = PUBLIC_ASSETS_DIR / "generated" / safe_target
    if not overwrite and (export_dir.exists() or public_dir.exists()):
        raise AssetPipelineError(
            f"Export target already exists: {safe_target}",
            code="export_exists",
            status_code=409,
        )
    if overwrite and export_dir.exists():
        shutil.rmtree(export_dir)
    if overwrite and public_dir.exists():
        shutil.rmtree(public_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for filename in ("processed.png", "alpha.png", "sheet.png", "metadata.json", "source.png"):
        source_file = preview_dir / filename
        if source_file.exists():
            shutil.copy2(source_file, export_dir / filename)
            shutil.copy2(source_file, public_dir / filename)
            copied.append(filename)

    export_payload = {
        "target": safe_target,
        "previewId": preview_id,
        "copiedFiles": copied,
        "publicPath": f"/assets/generated/{safe_target}",
        "metadata": metadata,
    }
    (export_dir / "export.json").write_text(json.dumps(export_payload, indent=2), encoding="utf-8")
    return export_payload


def paths_payload() -> dict[str, str]:
    return {
        "sources": str(SOURCES_DIR.relative_to(REPO_ROOT)),
        "publicAssets": str(PUBLIC_ASSETS_DIR.relative_to(REPO_ROOT)),
    }
