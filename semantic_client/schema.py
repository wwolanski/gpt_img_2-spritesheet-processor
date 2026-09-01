from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Mobility = Literal["static", "low", "medium", "high", "accessory"]
Persistence = Literal["always", "occasional"]

VALID_MOBILITY = {"static", "low", "medium", "high", "accessory"}
VALID_PERSISTENCE = {"always", "occasional"}


@dataclass(frozen=True)
class GroundingHint:
    frame: int
    bbox_2d: tuple[int, int, int, int]
    point_2d: tuple[int, int]
    confidence: float


@dataclass(frozen=True)
class ProposedPart:
    id: str
    label: str
    prompt: str
    mobility: Mobility
    persistence: Persistence
    grounded_frames: list[GroundingHint] = field(default_factory=list)


SPRITE_PARTS_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "parts": {
            "type": "array",
            "minItems": 0,
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "prompt": {"type": "string"},
                    "mobility": {"type": "string", "enum": sorted(VALID_MOBILITY)},
                    "persistence": {"type": "string", "enum": sorted(VALID_PERSISTENCE)},
                    "grounded_frames": {
                        "type": "array",
                        "minItems": 0,
                        "maxItems": 32,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "frame": {"type": "integer", "minimum": 0},
                                "bbox_2d": {
                                    "type": "array",
                                    "prefixItems": [
                                        {"type": "integer", "minimum": 0, "maximum": 1000},
                                        {"type": "integer", "minimum": 0, "maximum": 1000},
                                        {"type": "integer", "minimum": 0, "maximum": 1000},
                                        {"type": "integer", "minimum": 0, "maximum": 1000},
                                    ],
                                    "minItems": 4,
                                    "maxItems": 4,
                                },
                                "point_2d": {
                                    "type": "array",
                                    "prefixItems": [
                                        {"type": "integer", "minimum": 0, "maximum": 1000},
                                        {"type": "integer", "minimum": 0, "maximum": 1000},
                                    ],
                                    "minItems": 2,
                                    "maxItems": 2,
                                },
                                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                            },
                            "required": ["frame", "bbox_2d", "point_2d", "confidence"],
                        },
                    },
                },
                "required": ["id", "label", "prompt", "mobility", "persistence", "grounded_frames"],
            },
        }
    },
    "required": ["parts"],
}


def response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "sprite_parts_grounding",
            "strict": True,
            "schema": SPRITE_PARTS_SCHEMA,
        },
    }


def parse_proposed_parts(data: dict[str, object], warnings: list[str], frame_count: int) -> list[ProposedPart]:
    parts: list[ProposedPart] = []
    seen: set[str] = set()
    for item in data.get("parts", []):
        if not isinstance(item, dict):
            continue
        part_id = normalize_id(str(item.get("id") or item.get("label") or ""))
        label = str(item.get("label") or part_id).strip()
        prompt = sanitize_prompt(str(item.get("prompt") or label or part_id).strip(), label, part_id)
        mobility = str(item.get("mobility") or "medium")
        persistence = str(item.get("persistence") or "always")
        if not part_id or part_id in seen or mobility not in VALID_MOBILITY or persistence not in VALID_PERSISTENCE:
            warnings.append(f"semantic proposer ignored invalid part: {label or part_id}")
            continue
        hints = parse_grounding_hints(item.get("grounded_frames", []), frame_count)
        parts.append(ProposedPart(part_id, label or part_id, prompt or label or part_id, mobility, persistence, hints))  # type: ignore[arg-type]
        seen.add(part_id)
    return parts


def parse_grounding_hints(value: object, frame_count: int) -> list[GroundingHint]:
    hints: list[GroundingHint] = []
    if not isinstance(value, list):
        return hints
    for item in value:
        if not isinstance(item, dict):
            continue
        frame = int_or_none(item.get("frame"))
        bbox = int_list(item.get("bbox_2d"), 4)
        point = int_list(item.get("point_2d"), 2)
        if frame is None or frame < 0 or frame >= frame_count or bbox is None or point is None:
            continue
        x1, y1, x2, y2 = [clamp_1000(v) for v in bbox]
        if x2 <= x1 or y2 <= y1:
            continue
        px, py = [clamp_1000(v) for v in point]
        confidence = float(item.get("confidence", 0.0) or 0.0)
        hints.append(GroundingHint(frame, (x1, y1, x2, y2), (px, py), max(0.0, min(1.0, confidence))))
    return hints


def normalize_id(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", value.lower().strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    for prefix in ("bee_", "wasp_", "sprite_", "character_", "creature_", "pirate_", "orc_"):
        if slug.startswith(prefix):
            slug = slug[len(prefix) :]
    return slug[:48]


def sanitize_prompt(prompt: str, label: str, part_id: str) -> str:
    lowered = prompt.lower()
    required = part_keywords(label, part_id)
    if required and not any(keyword in lowered for keyword in required):
        return label or part_id
    return prompt or label or part_id


def part_keywords(label: str, part_id: str) -> tuple[str, ...]:
    text = f"{label} {part_id}".lower()
    if "wing" in text:
        return ("wing",)
    if "head" in text:
        return ("head", "face")
    if "body" in text or "torso" in text or "abdomen" in text or "thorax" in text:
        return ("body", "torso", "abdomen", "thorax")
    if "leg" in text:
        return ("leg",)
    if "arm" in text:
        return ("arm",)
    if "sword" in text:
        return ("sword", "blade")
    return ()


def int_or_none(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def int_list(value: object, length: int) -> list[int] | None:
    if not isinstance(value, list) or len(value) != length:
        return None
    output: list[int] = []
    for item in value:
        parsed = int_or_none(item)
        if parsed is None:
            return None
        output.append(parsed)
    return output


def clamp_1000(value: int) -> int:
    return max(0, min(1000, int(value)))
