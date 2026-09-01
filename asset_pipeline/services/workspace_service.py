from __future__ import annotations

import re
import shutil
from hashlib import sha1
from pathlib import Path

from asset_pipeline.services.config import PREVIEWS_DIR

SAFE_ID_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")


def build_workspace_id(value: str) -> str:
    cleaned = SAFE_ID_PATTERN.sub("-", value).strip(".-")
    if not cleaned:
        raise ValueError("Workspace id cannot be empty.")
    if len(cleaned) <= 160:
        return cleaned
    digest = sha1(cleaned.encode("utf-8")).hexdigest()[:12]
    return f"{cleaned[:147]}-{digest}"


def require_workspace_id(value: str) -> str:
    if build_workspace_id(value) != value:
        raise ValueError(f"Invalid workspace id: {value}")
    return value


def preview_dir_for(preview_id: str) -> Path:
    preview_dir = (PREVIEWS_DIR / require_workspace_id(preview_id)).resolve()
    if PREVIEWS_DIR.resolve() not in preview_dir.parents:
        raise ValueError(f"Invalid preview id: {preview_id}")
    return preview_dir


def reset_preview_dir(preview_id: str) -> Path:
    preview_dir = preview_dir_for(preview_id)
    if preview_dir.exists():
        shutil.rmtree(preview_dir)
    preview_dir.mkdir(parents=True, exist_ok=True)
    return preview_dir


def preview_job_id(batch_id: str, source_name: str, pipeline_id: str) -> str:
    source_stem = source_name.rsplit(".", 1)[0]
    return build_workspace_id(f"{batch_id}-{source_stem}-{pipeline_id}")
