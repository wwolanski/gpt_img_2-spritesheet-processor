from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    maskModel: str
    device: str
    half: bool
    version: str
    models: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SpriteFrame(BaseModel):
    index: int
    width: int
    height: int
    rgbPngBase64: str


class SemanticPartSpec(BaseModel):
    id: str
    label: str
    prompt: str
    mobility: Literal["static", "low", "medium", "high", "accessory"]
    persistence: Literal["always", "occasional"]


class PartEdit(BaseModel):
    frame: int
    partId: str
    type: Literal["positive_point", "negative_point", "bbox"]
    x: float | None = None
    y: float | None = None
    box: list[float] | None = None


class SegmentOptions(BaseModel):
    maskEncoding: Literal["rle"] = "rle"
    confidenceThreshold: float = 0.25
    maskModel: str = "sam3"


class SegmentRequest(BaseModel):
    frames: list[SpriteFrame]
    parts: list[SemanticPartSpec]
    edits: list[PartEdit] = Field(default_factory=list)
    options: SegmentOptions = Field(default_factory=SegmentOptions)


class SegmentPartResult(BaseModel):
    id: str
    label: str
    confidence: float
    presence: list[bool]
    boxes: list[list[int] | None]
    masks: list[str]
    warnings: list[str]


class SegmentResponse(BaseModel):
    parts: list[SegmentPartResult]
