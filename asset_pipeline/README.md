# Asset Pipeline Workbench

Cel: szybkie testowanie 3 źródeł przez wiele pipeline, tweak per pipeline, compare score, export dopiero po approve.

## Mental model

- `source`: plik z `asset_pipeline/sources/`.
- `profile`: preset bazowy pod typ inputu: `outline`, `thick-outline`, `pixelart`.
- `pipeline`: konkretny przepływ etapów. Każdy pipeline ma własne tweak values w UI.
- `stage`: osobny service w `asset_pipeline/services/`.

## Pipeline profiles

Config lives in `asset_pipeline/config/`.

- `defaults.json`: neutral defaults, profile presets, worker count, pipeline order.
- `stage_registry.json`: canonical service order plus stage labels/configurability.
- `pipelines/*.json`: one dedicated config file per pipeline profile.

Each pipeline profile lists every service in registry order with `included: true/false`.
UI uses that backend payload directly. Filled dot = stage included in current pipeline, empty dot = stage available but not included.
Configurable stages also show ON/OFF switch in Settings.

- `greenscreen-clean`: chroma mask + despill by default.
- `outline-ink`: chroma mask + despill + outline by default.
- `pixel-solid`: pixel mask + despill by default.
- `distance-classic`: distance mask + despill by default; outline available but OFF.
- `rembg-hybrid`: chroma mask + rembg mask + despill by default, enabled only when `rembg` works.

## Services

- `config.py`: loads JSON config, validates stage order, resolves stage toggles.
- `chroma_service.py`: HSV/distance/pixel alpha masks.
- `despill_service.py`: green edge cleanup.
- `outline_service.py`: dark edge color + outline compose.
- `frame_service.py`: component detect, wide-frame split, normalized sheet.
- `stabilization_service.py`: alpha island cleanup, flow-guided deflicker, temporal deflicker, edge extrusion.
- `metric_service.py`: score + leak/spill/alpha metrics.
- `upscale_service.py`: nearest/AuraSR upscale.
- `interpolation_client.py`: Practical-RIFE HTTP client; doubles normalized loop frames after Qwen3 and before SAM3.
- `runner_service.py`: composes services, runs compare with `ProcessPoolExecutor`.
- `storage_service.py`: safe source/preview/export IO.

## Semantic editor presets

Presets are runtime data and are stored by default in
`.runtime/semantic_editor_presets.json`; the tracked
`config/semantic_editor_presets.example.json` is only a template. Override the
location with `ASSET_PIPELINE_PRESETS_FILE`. The file uses version 2, migrates
the old config file/version 1 on first read, and is written through an
exclusive lock plus an atomic replace so concurrent saves cannot leave a
partially written JSON file.

## Performance

Image math uses NumPy + OpenCV vector ops. Pandas is not useful here; data is dense pixels, not tables.

Compare uses multiple Python processes. Default max workers: `10`, clamped to task count and CPU count. UI calls one `/api/asset-pipeline/compare` request instead of N sequential process requests.

For max CPU use, run matrix compare: 3 sources x 4 enabled pipelines = 12 tasks, so 10 workers can run useful work at once. Single-source compare has only 4 tasks when `rembg` is disabled, so it cannot use 10 workers without fake work.

Current hot path:

- OpenCV native `floodFill` for border-connected masks.
- squared RGB distance for threshold masks, no `sqrt` except legacy distance alpha.
- NumPy/OpenCV vector ops for dense pixel math.
- OpenCV thread cap per worker to avoid oversubscription.
- low PNG compression for faster preview writes.

GPU is not used. Current inputs are small 1.5-2 MB spritesheets; CPU OpenCV/NumPy avoids GPU transfer overhead and works with standard wheels. CUDA would only make sense for much larger batches/images and would require a CUDA OpenCV/CuPy stack.

RIFE and SAM3 are exceptions: both run in separate long-lived GPU services. Start `frame_interpolation_service/start.sh` on port `8775` before processing. If unavailable, interpolation reports a warning and leaves original frame count unchanged.

## UI

Preview files are transient runtime data. By default, Python returns PNGs inline and the dev server keeps them in RAM only.
Approved exports are the first durable write: `asset_pipeline/workbench/exports/` and `client/public/assets/generated/`.
For AI/VSCode debugging, use disk-backed CLI previews:

```bash
printf '{"pipelineId":"distance-classic","options":{"profile":"outline"}}' \
  | .venv/bin/python asset_pipeline/pipeline_tool.py process \
    --source pirate_outline.png \
    --preview-id debug-distance \
    --preview-storage disk
```

Open outputs in:

```text
asset_pipeline/workbench/previews/debug-distance/processed.png
asset_pipeline/workbench/previews/debug-distance/sheet.png
asset_pipeline/workbench/previews/debug-distance/metadata.json
```

```bash
cd client
npm ci
npm run dev
```

Open:

```text
http://localhost:5174
```

Flow:

1. Pick source.
2. Pick profile.
3. Pick pipeline and tweak its controls.
4. Switch pipeline and tweak another one.
5. Run compare.
6. Click best visual result.
7. Approve + export.

## CLI

```bash
.venv/bin/python asset_pipeline/pipeline_tool.py describe
.venv/bin/python asset_pipeline/pipeline_tool.py validate-config
.venv/bin/python asset_pipeline/pipeline_tool.py list-sources
printf '{"pipelineId":"outline-ink","options":{"profile":"outline","outlineWidth":3}}' \
  | .venv/bin/python asset_pipeline/pipeline_tool.py process --source pirate_outline.png --preview-id test-outline
printf '{"pipelineId":"distance-classic","options":{"profile":"outline"}}' \
  | .venv/bin/python asset_pipeline/pipeline_tool.py process --source pirate_outline.png --preview-id debug-distance --preview-storage disk
printf '{"options":{"profile":"auto"}}' \
  | .venv/bin/python asset_pipeline/pipeline_tool.py compare --source pirate_outline.png --batch-id test-compare --workers 10
printf '{"options":{"profile":"auto"}}' \
  | .venv/bin/python asset_pipeline/pipeline_tool.py compare-matrix \
    --source pirate_outline.png \
    --source pirate_outline_superthick.png \
    --source pirate_pixelart.png \
    --batch-id test-matrix \
    --workers 10
```

## Python deps

```bash
.venv/bin/python -m pip install -r asset_pipeline/requirements.txt
# Opcjonalne rembg/AuraSR/Qwen:
.venv/bin/python -m pip install -r asset_pipeline/requirements-optional.txt
```

`rembg` i `AuraSR` są optional. Core pipeline działa bez nich.
