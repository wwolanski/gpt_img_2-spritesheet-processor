from __future__ import annotations


from asset_pipeline.services.semantic_models import FrameSequence, SemanticGrounding, SemanticPartSpec
from semantic_client import propose_sprite_parts
from semantic_client.schema import ProposedPart


def propose_parts(
    sequence: FrameSequence,
    warnings: list[str],
    manual_parts: list[dict[str, object]] | None = None,
    diagnostics: dict[str, object] | None = None,
) -> list[SemanticPartSpec]:
    manual_specs = parse_specs({"parts": manual_parts or []}, warnings)
    if manual_specs:
        if diagnostics is not None:
            diagnostics.update({"enabled": False, "status": "manual", "hit": False, "id": None, "path": None})
        return ensure_unique_ids(manual_specs)
    return ensure_unique_ids(
        [
            to_semantic_part(part)
            for part in propose_sprite_parts(sequence.sam_rgb_frames, warnings, diagnostics=diagnostics)
        ]
    )


def to_semantic_part(part: ProposedPart) -> SemanticPartSpec:
    return SemanticPartSpec(
        part.id,
        part.label,
        part.prompt,
        part.mobility,
        part.persistence,
        [SemanticGrounding(hint.frame, hint.bbox_2d, hint.point_2d, hint.confidence) for hint in part.grounded_frames],
        {},
    )


def parse_specs(data: dict[str, object], warnings: list[str]) -> list[SemanticPartSpec]:
    specs: list[SemanticPartSpec] = []
    valid_mobility = {"static", "low", "medium", "high", "accessory"}
    valid_persistence = {"always", "occasional"}
    for item in data.get("parts", []):
        if not isinstance(item, dict):
            continue
        part_id = str(item.get("id", item.get("label", ""))).strip().lower().replace(" ", "_")
        label = str(item.get("label", part_id)).strip()
        prompt = str(item.get("prompt", label)).strip()
        mobility = str(item.get("mobility", "medium"))
        persistence = str(item.get("persistence", "always"))
        if not part_id or mobility not in valid_mobility or persistence not in valid_persistence:
            warnings.append(f"semantic proposer ignored invalid part: {label or part_id}")
            continue
        specs.append(
            SemanticPartSpec(
                part_id,
                label or part_id,
                prompt or label or part_id,
                mobility,
                persistence,
                parse_grounding(item),
                normalize_stabilize_settings(item.get("stabilizeSettings", item.get("stabilize", {}))),
            )
        )
    return specs


def ensure_unique_ids(specs: list[SemanticPartSpec]) -> list[SemanticPartSpec]:
    seen: set[str] = set()
    result: list[SemanticPartSpec] = []
    for spec in specs:
        base_id = normalize_id(spec.id) or normalize_id(spec.label) or "part"
        next_id = base_id
        if next_id in seen:
            label_id = normalize_id(spec.label)
            if label_id and label_id not in seen:
                next_id = label_id
            elif label_id and f"{base_id}_{label_id}" not in seen:
                next_id = f"{base_id}_{label_id}"
            else:
                suffix = 2
                while f"{base_id}_{suffix}" in seen:
                    suffix += 1
                next_id = f"{base_id}_{suffix}"
        seen.add(next_id)
        spec.id = next_id
        result.append(spec)
    return result


def normalize_id(value: str) -> str:
    return "_".join(str(value).strip().lower().replace("-", "_").split())


def parse_grounding(item: dict[str, object]) -> list[SemanticGrounding]:
    value = item.get("grounding", item.get("grounded_frames", []))
    if not isinstance(value, list):
        return []
    hints: list[SemanticGrounding] = []
    for hint in value:
        if not isinstance(hint, dict):
            continue
        bbox = hint.get("bbox_2d")
        point = hint.get("point_2d")
        if not (isinstance(bbox, list) and len(bbox) == 4 and isinstance(point, list) and len(point) == 2):
            continue
        try:
            hints.append(
                SemanticGrounding(
                    int(hint.get("frame", 0)),
                    tuple(int(value) for value in bbox),  # type: ignore[arg-type]
                    tuple(int(value) for value in point),  # type: ignore[arg-type]
                    float(hint.get("confidence", 1.0) or 1.0),
                )
            )
        except (TypeError, ValueError):
            continue
    return hints


def normalize_stabilize_settings(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    settings: dict[str, object] = {}
    for key in ("enabled", "repairEnabled"):
        if key in value:
            settings[key] = bool(value[key])
    for key in ("repairSearchScale", "patchLockStrength", "medianStrength"):
        if key not in value:
            continue
        try:
            settings[key] = float(value[key])
        except (TypeError, ValueError):
            continue
    return settings
