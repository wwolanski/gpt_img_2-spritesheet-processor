from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from asset_pipeline.services.models import FrameBox

Mobility = Literal["static", "low", "medium", "high", "accessory"]
Persistence = Literal["always", "occasional"]


@dataclass(frozen=True)
class SemanticGrounding:
    frame: int
    bbox_2d: tuple[int, int, int, int]
    point_2d: tuple[int, int]
    confidence: float


@dataclass
class FrameSequence:
    raw_rgb_frames: list[np.ndarray]
    base_alpha_frames: list[np.ndarray]
    semantic_alpha_frames: list[np.ndarray]
    sam_rgb_frames: list[np.ndarray]
    final_rgba_frames: list[np.ndarray]
    boxes: list[FrameBox]
    semantic_offsets: list[tuple[int, int]]
    key_color: tuple[int, int, int]


@dataclass
class SemanticPartSpec:
    id: str
    label: str
    prompt: str
    mobility: Mobility
    persistence: Persistence
    grounding: list[SemanticGrounding] = field(default_factory=list)
    stabilize_settings: dict[str, object] = field(default_factory=dict)


@dataclass
class PartTrack:
    id: str
    label: str
    color: tuple[int, int, int]
    mobility: Mobility
    persistence: Persistence
    confidence: float
    masks: list[np.ndarray]
    boxes: list[FrameBox | None]
    warnings: list[str] = field(default_factory=list)
    presence: list[bool] = field(default_factory=list)
    mask_statuses: list[str] = field(default_factory=list)
    frame_metrics: list[dict[str, object]] = field(default_factory=list)
    stabilize_settings: dict[str, object] = field(default_factory=dict)


@dataclass
class SemanticMetrics:
    part_presence_failures: int = 0
    part_area_jitter: float = 0.0
    part_centroid_jitter: float = 0.0
    part_edge_jitter: float = 0.0
    semantic_confidence_min: float = 0.0
    manual_review_required: bool = False
