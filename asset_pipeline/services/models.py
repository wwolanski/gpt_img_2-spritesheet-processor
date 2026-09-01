from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FrameBox:
    index: int
    x: int
    y: int
    width: int
    height: int
    area: int
    center_x: float
    center_y: float


@dataclass
class PreviewFiles:
    processed: str
    alpha: str
    sheet: str
    metadata: str


@dataclass
class Metrics:
    score: float
    border_leak_ratio: float
    green_spill_ratio: float
    edge_alpha_ratio: float
    tiny_component_count: int
    component_count: int
    opaque_coverage: float


@dataclass(frozen=True)
class PipelineStage:
    id: str
    included: bool


@dataclass(frozen=True)
class StageDefinition:
    id: str
    label: str
    description: str
    configurable: bool


@dataclass(frozen=True)
class PipelineProfile:
    id: str
    label: str
    description: str
    profile_hint: str
    stages: tuple[PipelineStage, ...]
    option_overrides: dict[str, object]
    optional: str | None = None
