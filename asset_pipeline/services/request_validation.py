from __future__ import annotations

import os
import re
from typing import cast

from asset_pipeline.services.contracts import (
    API_DEFAULT_LIMITS,
    SOURCE_NAME_REGEX,
    SUPPORTED_IMAGE_SUFFIXES,
    JsonObject,
)
from asset_pipeline.services.errors import ValidationError


def _env_limit(name: str, fallback: int) -> int:
    try:
        value = int(os.environ.get(name, fallback))
    except (TypeError, ValueError):
        return fallback
    return value if value > 0 else fallback


MAX_REQUEST_BODY_BYTES = _env_limit("ASSET_PIPELINE_MAX_REQUEST_BODY_BYTES", API_DEFAULT_LIMITS["maxRequestBodyBytes"])
MAX_SOURCES = _env_limit("ASSET_PIPELINE_MAX_SOURCES", API_DEFAULT_LIMITS["maxSources"])
MAX_WORKERS = _env_limit("ASSET_PIPELINE_MAX_WORKERS", API_DEFAULT_LIMITS["maxWorkers"])
MAX_PIPELINES = _env_limit("ASSET_PIPELINE_MAX_PIPELINES", API_DEFAULT_LIMITS["maxPipelines"])
SOURCE_NAME_PATTERN = re.compile(SOURCE_NAME_REGEX)


def validate_source_name(value: object) -> str:
    if not isinstance(value, str) or not SOURCE_NAME_PATTERN.fullmatch(value):
        raise ValidationError("source must be a filename, not a path")
    if not value.casefold().endswith(SUPPORTED_IMAGE_SUFFIXES):
        raise ValidationError("source must be a supported image filename")
    return value


def validate_source_names(values: object) -> list[str]:
    if not isinstance(values, list):
        raise ValidationError("sources must be an array")
    if not values:
        raise ValidationError("sources must contain at least one filename")
    if len(values) > MAX_SOURCES:
        raise ValidationError(f"sources cannot contain more than {MAX_SOURCES} items")
    result = [validate_source_name(value) for value in values]
    if len(set(result)) != len(result):
        raise ValidationError("sources cannot contain duplicates")
    return result


def validate_workers(value: object) -> int:
    try:
        workers = int(value)
    except (TypeError, ValueError) as error:
        raise ValidationError("workers must be an integer") from error
    if workers < 1 or workers > MAX_WORKERS:
        raise ValidationError(f"workers must be between 1 and {MAX_WORKERS}")
    return workers


def validate_pipeline_ids(value: object) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValidationError("pipelineIds must be an array")
    if len(value) > MAX_PIPELINES:
        raise ValidationError(f"pipelineIds cannot contain more than {MAX_PIPELINES} items")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValidationError("pipelineIds must contain non-empty strings")
    if len(set(value)) != len(value):
        raise ValidationError("pipelineIds cannot contain duplicates")
    return value


def validate_payload(value: object) -> JsonObject:
    if not isinstance(value, dict):
        raise ValidationError("request body must be a JSON object")
    options = value.get("options", {})
    if not isinstance(options, dict):
        raise ValidationError("options must be an object")
    return cast(JsonObject, value)
