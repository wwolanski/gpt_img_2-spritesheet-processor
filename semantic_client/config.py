from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Qwen3VLConfig:
    base_url: str
    api_key: str
    model: str | None
    model_auto_pattern: str
    timeout_seconds: float
    temperature: float
    top_p: float
    max_tokens: int
    seed: int | None
    use_structured_output: bool
    allow_json_object_fallback: bool


def load_config() -> Qwen3VLConfig:
    seed = env_value("SEMANTIC_CLIENT_QWEN_SEED")
    return Qwen3VLConfig(
        base_url=(env_value("SEMANTIC_CLIENT_QWEN_BASE_URL", "http://localhost:1234/v1") or "").rstrip("/"),
        api_key=env_value("SEMANTIC_CLIENT_QWEN_API_KEY", "lm-studio") or "",
        model=empty_to_none(env_value("SEMANTIC_CLIENT_QWEN_MODEL")),
        model_auto_pattern=env_value("SEMANTIC_CLIENT_QWEN_MODEL_AUTO", "qwen") or "",
        timeout_seconds=max(1.0, float(env_value("SEMANTIC_CLIENT_QWEN_TIMEOUT_SECONDS", "180") or "180")),
        temperature=float(env_value("SEMANTIC_CLIENT_QWEN_TEMPERATURE", "0.05") or "0.05"),
        top_p=float(env_value("SEMANTIC_CLIENT_QWEN_TOP_P", "0.8") or "0.8"),
        max_tokens=max(256, int(env_value("SEMANTIC_CLIENT_QWEN_MAX_TOKENS", "2048") or "2048")),
        seed=int(seed) if seed else None,
        use_structured_output=env_value("SEMANTIC_CLIENT_STRUCTURED_OUTPUT", "1") == "1",
        allow_json_object_fallback=env_value("SEMANTIC_CLIENT_ALLOW_JSON_OBJECT_FALLBACK", "0") == "1",
    )


def env_value(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
