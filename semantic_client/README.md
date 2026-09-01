# Semantic Client

OpenAI-compatible Qwen3 VL client for `semantic-propose`.

## Runtime Contract

- Server: `http://localhost:1234/v1`
- SDK: `openai-python`
- Input: up to 8 neutral-matte RGB frame crops as `image_url` data URIs.
- Output: strict JSON schema with sprite parts and Qwen grounding hints.
- Coordinates: `relative_1000`, per frame, not contact sheet.
- Grounding consumed by SAM3 as bbox + positive point visual prompts.

## Output Shape

```json
{
  "parts": [
    {
      "id": "wings",
      "label": "wings",
      "prompt": "wasp transparent wings",
      "mobility": "high",
      "persistence": "always",
      "grounded_frames": [
        {
          "frame": 0,
          "bbox_2d": [220, 80, 780, 430],
          "point_2d": [510, 240],
          "confidence": 0.86
        }
      ]
    }
  ]
}
```

## Env

See `.env.example`.

Important values:

```text
SEMANTIC_CLIENT_QWEN_BASE_URL=http://localhost:1234/v1
SEMANTIC_CLIENT_QWEN_MODEL=<exact model id, optional>
SEMANTIC_CLIENT_QWEN_MODEL_AUTO=qwen
SEMANTIC_CLIENT_STRUCTURED_OUTPUT=1
SEMANTIC_CLIENT_QWEN_TEMPERATURE=0.05
ASSET_PIPELINE_QWEN_GROUNDING_MIN_CONFIDENCE=0.35
SEMANTIC_CLIENT_QWEN_CACHE=1
SEMANTIC_CLIENT_QWEN_CACHE_DIR=semantic_client/.cache/qwen3_vl
SEMANTIC_CLIENT_QWEN_CACHE_STRICT_CONFIG=0
```

Qwen grounding is treated as a visual hint, not ground truth. The asset pipeline validates each hinted bbox/point against the detected foreground alpha before sending it to SAM3. Low-confidence hints are ignored.

Qwen responses are cached on disk by frame pixels, prompt text, and schema. Cache hit returns parsed parts without calling the OpenAI-compatible server. Concurrent identical requests share a file lock while the request is active. Failed requests are not cached. Set `SEMANTIC_CLIENT_QWEN_CACHE_STRICT_CONFIG=1` only when model/generation config must be part of the cache key.

If local OpenAI-compatible server rejects `response_format.type=json_schema`, enable structured output / JSON schema in that server. For LM Studio-compatible runtimes, load Qwen3 VL 8B, enable structured output support when available, then verify:

```bash
curl http://localhost:1234/v1/models
```

If strict schema remains unsupported, temporary debug fallback:

```text
SEMANTIC_CLIENT_ALLOW_JSON_OBJECT_FALLBACK=1
```

Strict schema should stay enabled for real evaluation.
