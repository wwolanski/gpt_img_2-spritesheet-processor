from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class HealthResponse(BaseModel):
    status: str
    provider: str = "practical-rife"
    model: str
    device: str
    half: bool
    version: str = "1"
    factor: int = 2
    warnings: list[str] = Field(default_factory=list)


class SpriteFrame(BaseModel):
    index: int
    width: int
    height: int
    rgbaPngBase64: str


class InterpolationOptions(BaseModel):
    factor: Literal[2] = 2
    loop: bool = True
    alphaMode: Literal["rife", "linear"] = "rife"
    matteColor: tuple[int, int, int] = (128, 128, 128)
    scale: float = Field(default=1.0, ge=0.25, le=4.0)

    @model_validator(mode="after")
    def validate_matte(self) -> "InterpolationOptions":
        if any(channel < 0 or channel > 255 for channel in self.matteColor):
            raise ValueError("matteColor channels must be between 0 and 255")
        return self


class InterpolationRequest(BaseModel):
    frames: list[SpriteFrame]
    options: InterpolationOptions = Field(default_factory=InterpolationOptions)

    @model_validator(mode="after")
    def validate_frames(self) -> "InterpolationRequest":
        if not 2 <= len(self.frames) <= 16:
            raise ValueError("frame count must be between 2 and 16")
        sizes = {(frame.width, frame.height) for frame in self.frames}
        if len(sizes) != 1:
            raise ValueError("all frames must use one normalized size")
        if any(frame.width <= 0 or frame.height <= 0 for frame in self.frames):
            raise ValueError("frame dimensions must be positive")
        return self


class InterpolatedFrame(BaseModel):
    index: int
    sourceFrame: int
    nextSourceFrame: int
    interpolated: bool
    rgbaPngBase64: str


class InterpolationResponse(BaseModel):
    factor: int = 2
    loop: bool
    sourceFrameCount: int
    outputFrameCount: int
    frames: list[InterpolatedFrame]
