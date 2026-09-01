"""Typed JSON boundary objects for the local pipeline API and CLI."""

from __future__ import annotations

from typing import Final, NotRequired, TypeAlias, TypedDict

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]

API_DEFAULT_LIMITS: Final = {
    "maxRequestBodyBytes": 4 * 1024 * 1024,
    "maxSources": 32,
    "maxWorkers": 16,
    "maxPipelines": 16,
}
SOURCE_NAME_REGEX: Final = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,254}$"
SUPPORTED_IMAGE_SUFFIXES: Final = (".png", ".jpg", ".jpeg", ".webp")


class PipelineRequest(TypedDict, total=False):
    source: str
    pipelineId: str
    pipelineIds: list[str]
    sources: list[str]
    workers: int
    options: JsonObject


class ProcessRequest(PipelineRequest):
    source: str
    options: NotRequired[JsonObject]


class SemanticPresetRequest(TypedDict):
    name: str
    settings: JsonObject


class ExportRequest(TypedDict):
    previewId: str
    targetName: str
    overwrite: NotRequired[bool]
