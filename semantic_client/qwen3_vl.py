from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import numpy as np

from semantic_client.config import Qwen3VLConfig, env_value, load_config
from semantic_client.prompts import SYSTEM_PROMPT, user_prompt
from semantic_client.schema import ProposedPart, parse_proposed_parts, response_format


def propose_sprite_parts(
    frames: list[np.ndarray],
    warnings: list[str],
    config: Qwen3VLConfig | None = None,
    diagnostics: dict[str, object] | None = None,
) -> list[ProposedPart]:
    cfg = config or load_config()
    if not frames:
        warnings.append("semantic proposer skipped: no frames for Qwen3-VL")
        update_cache_diagnostics(diagnostics, cfg, [], "skipped", None)
        return []
    prompt_frames = frames[:8]
    update_cache_diagnostics(diagnostics, cfg, prompt_frames, "miss", None)
    cached = read_cached_response(prompt_frames, cfg, warnings, diagnostics)
    if cached is not None:
        return parse_proposed_parts(cached, warnings, len(prompt_frames))
    with cache_lock(prompt_frames, cfg, warnings):
        cached = read_cached_response(prompt_frames, cfg, warnings, diagnostics)
        if cached is not None:
            return parse_proposed_parts(cached, warnings, len(prompt_frames))
        return request_sprite_parts(prompt_frames, warnings, cfg, diagnostics)


def request_sprite_parts(
    frames: list[np.ndarray],
    warnings: list[str],
    cfg: Qwen3VLConfig,
    diagnostics: dict[str, object] | None = None,
) -> list[ProposedPart]:
    try:
        from openai import APIError, APITimeoutError, OpenAI
    except ImportError:
        warnings.append("semantic proposer skipped: openai-python not installed")
        return []

    client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key, timeout=cfg.timeout_seconds, max_retries=0)
    try:
        model_id = cfg.model or choose_qwen_model(client, cfg)
    except Exception as error:
        warnings.append(f"semantic proposer skipped: Qwen3-VL model lookup failed ({error})")
        return []
    if not model_id:
        warnings.append("semantic proposer skipped: Qwen3-VL model not available")
        return []

    content = build_content(frames)
    create_kwargs: dict[str, object] = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        "temperature": cfg.temperature,
        "top_p": cfg.top_p,
        "max_tokens": cfg.max_tokens,
    }
    if cfg.seed is not None:
        create_kwargs["seed"] = cfg.seed
    if cfg.use_structured_output:
        create_kwargs["response_format"] = response_format()

    try:
        completion = client.chat.completions.create(**create_kwargs)
    except (APIError, APITimeoutError, ValueError) as error:
        if not cfg.allow_json_object_fallback:
            warnings.append(f"semantic proposer skipped: Qwen3-VL structured output failed ({error})")
            return []
        create_kwargs["response_format"] = {"type": "json_object"}
        try:
            completion = client.chat.completions.create(**create_kwargs)
        except Exception as fallback_error:
            warnings.append(f"semantic proposer skipped: Qwen3-VL JSON fallback failed ({fallback_error})")
            return []
    except Exception as error:
        warnings.append(f"semantic proposer skipped: Qwen3-VL request failed ({error})")
        return []

    message = completion.choices[0].message
    raw = message.content if isinstance(message.content, str) else ""
    parsed = parse_json_response(raw, warnings)
    if parsed is None:
        return []
    cache_id = write_cached_response(frames, cfg, parsed, raw, model_id, warnings)
    update_cache_diagnostics(diagnostics, cfg, frames, "miss", cache_id)
    return parse_proposed_parts(parsed, warnings, len(frames))


def choose_qwen_model(client: object, config: Qwen3VLConfig) -> str | None:
    models = client.models.list()
    pattern = re.compile(config.model_auto_pattern, re.IGNORECASE)
    for model in models.data:
        model_id = str(getattr(model, "id", ""))
        if pattern.search(model_id):
            return model_id
    return str(models.data[0].id) if models.data else None


def build_content(frames: list[np.ndarray]) -> list[dict[str, object]]:
    content: list[dict[str, object]] = [{"type": "text", "text": user_prompt(len(frames))}]
    for index, frame in enumerate(frames):
        content.append({"type": "text", "text": f"Frame {index}:"})
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{encode_png_base64(frame)}",
                    "detail": "high",
                },
            }
        )
    return content


def parse_json_response(raw: str, warnings: list[str]) -> dict[str, object] | None:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            warnings.append("semantic proposer skipped: Qwen3-VL returned invalid JSON")
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            warnings.append("semantic proposer skipped: Qwen3-VL returned invalid JSON")
            return None
    if not isinstance(parsed, dict):
        warnings.append("semantic proposer skipped: Qwen3-VL JSON root is not object")
        return None
    return parsed


def encode_png_base64(rgb: np.ndarray) -> str:
    import base64
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.fromarray(rgb.astype(np.uint8), mode="RGB").save(buffer, format="PNG", compress_level=1)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def cache_enabled() -> bool:
    return env_value("SEMANTIC_CLIENT_QWEN_CACHE", "1") != "0"


def cache_dir() -> Path:
    default = str(Path(__file__).resolve().parent / ".cache" / "qwen3_vl")
    return Path(env_value("SEMANTIC_CLIENT_QWEN_CACHE_DIR", default) or default)


def strict_config_cache_key() -> bool:
    return env_value("SEMANTIC_CLIENT_QWEN_CACHE_STRICT_CONFIG", "0") == "1"


def cache_key(frames: list[np.ndarray], config: Qwen3VLConfig) -> str:
    digest = hashlib.sha256()
    params = {
        "version": 2,
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": user_prompt(len(frames)),
        "schema": "sprite_parts_grounding_v1",
    }
    if strict_config_cache_key():
        params.update(
            {
                "model": config.model,
                "model_auto_pattern": config.model_auto_pattern,
                "temperature": config.temperature,
                "top_p": config.top_p,
                "max_tokens": config.max_tokens,
                "seed": config.seed,
                "use_structured_output": config.use_structured_output,
            }
        )
    digest.update(json.dumps(params, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    for frame in frames:
        array = np.ascontiguousarray(frame.astype(np.uint8))
        digest.update(str(array.shape).encode("ascii"))
        digest.update(array.tobytes())
    return digest.hexdigest()


def cache_path(frames: list[np.ndarray], config: Qwen3VLConfig) -> Path:
    return cache_dir() / f"{cache_key(frames, config)}.json"


def read_cached_payload(
    frames: list[np.ndarray], config: Qwen3VLConfig, warnings: list[str]
) -> dict[str, object] | None:
    path = cache_path(frames, config)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        warnings.append(f"semantic proposer cache ignored: {error}")
        return None
    return payload if isinstance(payload, dict) else None


def read_cached_response(
    frames: list[np.ndarray],
    config: Qwen3VLConfig,
    warnings: list[str],
    diagnostics: dict[str, object] | None = None,
) -> dict[str, object] | None:
    if not cache_enabled():
        update_cache_diagnostics(diagnostics, config, frames, "disabled", None)
        return None
    path = cache_path(frames, config)
    payload = read_cached_payload(frames, config, warnings)
    if payload is None:
        return None
    parsed = payload.get("parsed")
    if not isinstance(parsed, dict):
        return None
    cache_id = cache_payload_id(payload)
    if payload.get("id") != cache_id:
        payload["id"] = cache_id
        write_cache_payload(path, payload, warnings)
    update_cache_diagnostics(diagnostics, config, frames, "hit", cache_id)
    return parsed


def write_cached_response(
    frames: list[np.ndarray],
    config: Qwen3VLConfig,
    parsed: dict[str, object],
    raw: str,
    model_id: str,
    warnings: list[str],
) -> str | None:
    if not cache_enabled():
        return None
    path = cache_path(frames, config)
    cache_id = random_cache_id()
    payload = {"id": cache_id, "created_at": time.time(), "model": model_id, "raw": raw, "parsed": parsed}
    write_cache_payload(path, payload, warnings)
    return cache_id


def random_cache_id() -> str:
    return secrets.token_hex(3)


def cache_payload_id(payload: dict[str, object]) -> str:
    value = payload.get("id")
    if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return value.lower()
    return random_cache_id()


def update_cache_diagnostics(
    diagnostics: dict[str, object] | None,
    config: Qwen3VLConfig,
    frames: list[np.ndarray],
    status: str,
    cache_id: str | None,
) -> None:
    if diagnostics is None:
        return
    path = cache_path(frames, config) if frames else None
    diagnostics.update(
        {
            "enabled": cache_enabled(),
            "status": status,
            "hit": status == "hit",
            "id": cache_id,
            "path": str(path) if path else None,
        }
    )


def write_cache_payload(path: Path, payload: dict[str, object], warnings: list[str]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(path)
    except OSError as error:
        warnings.append(f"semantic proposer cache write failed: {error}")


@contextmanager
def cache_lock(frames: list[np.ndarray], config: Qwen3VLConfig, warnings: list[str]) -> Iterator[None]:
    if not cache_enabled():
        yield
        return
    path = cache_dir() / f"{cache_key(frames, config)}.lock"
    handle = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("w", encoding="utf-8")
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except OSError as error:
            warnings.append(f"semantic proposer cache lock skipped: {error}")
        yield
    finally:
        if handle is not None:
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            handle.close()
            try:
                path.unlink(missing_ok=True)
            except OSError as error:
                warnings.append(f"semantic proposer cache lock cleanup failed: {error}")
