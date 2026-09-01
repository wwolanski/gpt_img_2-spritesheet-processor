from __future__ import annotations


from asset_pipeline.services.config import DEFAULT_OPTIONS, PIPELINE_PROFILES, PROFILE_PRESETS


def merge_options(
    raw_options: dict[str, object] | None, pipeline_id: str | None = None, source_name: str = ""
) -> dict[str, object]:
    options = dict(DEFAULT_OPTIONS)
    options.update(raw_options or {})
    profile = choose_profile(source_name, options)
    options.update(PROFILE_PRESETS.get(profile, {}))
    options.update(raw_options or {})
    if pipeline_id and pipeline_id in PIPELINE_PROFILES:
        options.update(PIPELINE_PROFILES[pipeline_id].option_overrides)
        options.update(raw_options or {})
    return options


def choose_profile(source_name: str, options: dict[str, object]) -> str:
    profile = str(options.get("profile", "auto"))
    if profile != "auto":
        return profile
    lowered = source_name.lower()
    if "pixel" in lowered:
        return "pixelart"
    if "superthick" in lowered or "thick" in lowered:
        return "thick-outline"
    return "outline"


def choose_pipeline(profile: str, requested_pipeline: str | None, _rembg_available: bool) -> str:
    if requested_pipeline:
        return requested_pipeline
    if profile == "pixelart":
        return "pixel-solid"
    if profile == "thick-outline":
        return "outline-ink"
    return "greenscreen-clean"


def detection_pipeline_for(final_pipeline: str, profile: str) -> str:
    if final_pipeline in {"outline-ink", "rembg-hybrid"}:
        return "greenscreen-clean"
    if final_pipeline in {"pixel-solid", "distance-classic"}:
        return final_pipeline
    return "pixel-solid" if profile == "pixelart" else "greenscreen-clean"
