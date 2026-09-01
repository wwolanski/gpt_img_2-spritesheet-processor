# SAM3 Service

Dlugowieczny serwis HTTP/FastAPI dla modeli maskowania semantycznego, uzywany przez `asset_pipeline` tylko przez endpointy HTTP. Domyslnie laduje SAM3, ale endpoint moze obslugiwac tez alternatywne providery wybierane w payloadzie.

Serwis jest celowo odizolowany od glownej aplikacji. Ma wlasne srodowisko:

```text
sam3_service/.venv/
```

Docker nie jest uzywany. CUDA/NVIDIA dziala bezposrednio na hoscie, co ulatwia debugowanie sterownikow, VRAM i procesu Pythona.

## Jak to dziala

`asset_pipeline` nie laduje modeli maskowania przy kazdym przetwarzaniu spritesheetu. Zamiast tego:

1. Uruchamiasz osobny serwer FastAPI przez `./start.sh` albo `./start_background.sh`.
2. FastAPI startuje proces Pythona i w `lifespan` laduje domyslny model raz.
3. Wybrany model zostaje w pamieci procesu przez caly czas dzialania serwera.
4. Kazde wywolanie `POST /v1/sprite/segment` uzywa juz zaladowanego modelu.
5. Model znika z RAM/VRAM dopiero po zatrzymaniu procesu serwera, np. przez `./stop.sh` albo `Ctrl+C`.

Czyli: model nie laduje sie tylko na czas jednego przetwarzania. Laduje sie przy pierwszym uzyciu i siedzi w pamieci jako long-lived runtime. Serwis utrzymuje jeden aktywny `maskModel`; wybranie innego providera zwalnia poprzedni runtime przed zaladowaniem nowego, aby ograniczyc zuzycie RAM/VRAM.

Przy `SAM3_DEVICE=cuda` model trafia na GPU/VRAM podczas inicjalizacji inferencji przez Ultralytics/PyTorch. Czesc danych pomocniczych i checkpoint cache zostaje w RAM. Przy `SAM3_DEVICE=cpu` model nie uzywa VRAM, ale inference jest wolniejszy.

## Modele

Obslugiwane `maskModel`:

- `sam3` - domyslny provider z text prompts i bbox prompts.
- `yolo26` - Ultralytics YOLO segmentation provider, domyslnie `models/yolo26x-seg.pt`.
- `vitmatte` - Hugging Face `hustvl/vitmatte-small-composition-1k`, wymaga trimap; serwis buduje trimap z bbox/point hintow albo fallback silhouette.
- `inspirinet` - zarezerwowana sciezka, obecnie degraded runtime z warningiem.

Domyslny model SAM3:

```text
sam3_service/models/sam3.1_multiplex_fp16.safetensors
```

Ultralytics `SAM(...)` wymaga sciezki `.pt` albo `.pth`, wiec serwis przy starcie robi lokalny cache:

```text
sam3_service/models/.cache/sam3.1_multiplex_fp16.<size>.<mtime>.pt
```

Oryginalny `.safetensors` zostaje zrodlem prawdy. Cache `.pt` jest tylko adapterem dla Ultralytics.

Niestandardowy model:

```bash
SAM3_MODEL_PATH=/absolute/path/to/model.safetensors ./start.sh
```

YOLO26:

```bash
SEMANTIC_MASK_MODEL=yolo26 YOLO26_MODEL_PATH=/absolute/path/to/yolo26x-seg.pt ./start.sh
```

`YOLO26_MODEL_PATH` moze wskazywac lokalny `.pt` albo nazwe modelu obslugiwana przez Ultralytics. Provider wybiera maski po bbox/point edit, dopasowaniu promptu do nazwy klasy albo fallbackiem do najwiekszej maski.

ViTMatte:

```bash
SEMANTIC_MASK_MODEL=vitmatte VITMATTE_MODEL_PATH=$PWD/models/vitmatte-small-composition-1k ./start.sh
```

Provider ViTMatte uzywa `VitMatteForImageMatting` z `transformers`. Najlepiej dziala, gdy request zawiera bbox + positive point dla czesci. Bez hintow buduje trimap z prostej sylwetki foreground i loguje fallback warning.

## Pierwsza instalacja

```bash
cd sam3_service
./setup_venv.sh
```

Ten skrypt tworzy `sam3_service/.venv/` i instaluje zaleznosci z `requirements.txt`, w tym PyTorch, Ultralytics, FastAPI, `safetensors` i CLIP wymagany przez SAM3 text prompts.

## Uruchomienie w terminalu

```bash
cd sam3_service
./start.sh
```

Serwer zostaje pod:

```text
http://127.0.0.1:8765
```

Sprawdzenie:

```bash
curl http://127.0.0.1:8765/health
```

Zatrzymanie: `Ctrl+C` w terminalu z serwerem.

## Uruchomienie w tle

```bash
cd sam3_service
./start_background.sh
curl http://127.0.0.1:8765/health
```

Tryb w tle zapisuje:

- `sam3_service.pid` - PID procesu serwera;
- `sam3_service.log` - logi startu i requestow.

Zatrzymanie:

```bash
./stop.sh
```

## Konfiguracja

Domyslne wartosci:

```text
SAM3_MODEL_PATH=sam3_service/models/sam3.1_multiplex_fp16.safetensors
SEMANTIC_MASK_MODEL=sam3
SAM3_DEVICE=cuda
SAM3_HALF=1
SAM3_IMGSZ=644
YOLO26_MODEL_PATH=sam3_service/models/yolo26x-seg.pt
YOLO26_DEVICE=$SAM3_DEVICE
YOLO26_HALF=$SAM3_HALF
YOLO26_IMGSZ=640
VITMATTE_MODEL_PATH=sam3_service/models/vitmatte-small-composition-1k
VITMATTE_DEVICE=$SAM3_DEVICE
VITMATTE_HALF=$SAM3_HALF
SAM3_HOST=127.0.0.1
SAM3_PORT=8765
SAM3_FALLBACK_MASKS=0
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
```

`SAM3_FALLBACK_MASKS=0` is the production default. When model inference fails, the service returns empty masks plus warnings instead of pretending a whole foreground silhouette is a semantic part. Set `SAM3_FALLBACK_MASKS=1` only for local degraded-mode debugging.

`SAM3_IMGSZ=644` is intentional for SAM3 stride 14. `640` gets rounded by Ultralytics and emits warnings on every request.

CPU/debug:

```bash
SAM3_DEVICE=cpu SAM3_HALF=0 ./start.sh
```

Inny port:

```bash
SAM3_PORT=8770 ./start.sh
```

Wtedy `asset_pipeline` musi wskazywac ten sam URL:

```bash
ASSET_PIPELINE_SAM3_URL=http://127.0.0.1:8770
```

Domyslny model wybierany przez backend bez UI:

```bash
ASSET_PIPELINE_SEMANTIC_MASK_MODEL=yolo26
```

## Health status

`GET /health` zwraca np.:

```json
{
  "status": "ok",
  "provider": "asset-pipeline-sam3",
  "model": "<module-root>/sam3_service/models/sam3.1_multiplex_fp16.safetensors",
  "maskModel": "sam3",
  "device": "cuda",
  "half": true,
  "version": "1",
  "models": ["sam3", "yolo26", "vitmatte", "inspirinet"],
  "warnings": []
}
```

`status=ok` oznacza, ze domyslny runtime zostal zaladowany i endpoint moze robic realna segmentacje.

`status=degraded` oznacza, ze domyslny runtime nie zaladowal sie poprawnie. Przy domyslnym `SAM3_FALLBACK_MASKS=0` endpoint zwraca wtedy puste maski i warnings. Fallback masks sa dostepne tylko po wlaczeniu `SAM3_FALLBACK_MASKS=1` do lokalnego debugowania; to nie jest produkcyjna segmentacja semantyczna. Przyczyny zwykle sa w `warnings`: brak modelu, zly format, problem CUDA, za malo VRAM albo blad zaleznosci.

## Endpointy

- `GET /health` - status serwisu i modelu.
- `POST /v1/sprite/segment` - segmentacja czesci spritesheetu.
- `GET /openapi.json` - schema OpenAPI generowana przez FastAPI.

`asset_pipeline` wysyla do `/v1/sprite/segment` klatki RGB jako PNG base64, liste czesci/prompty, edity bbox/point i `options.maskModel`. Serwis zwraca maski RLE, confidence, presence i warnings per part.

## Pamiec i VRAM

Najwazniejsza zasada: jeden proces serwera = jedno ladowanie kazdego uzytego modelu.

Koszt ladowania domyslnego modelu placisz przy starcie `./start.sh`; koszt alternatywnego modelu przy pierwszym request dla danego `maskModel`. Potem UI i pipeline nie czekaja za kazdym razem na import Torch, inicjalizacje CUDA i ladowanie wag.

VRAM pozostaje zajety dopoki serwer dziala. To jest oczekiwane. Jezeli potrzebujesz zwolnic VRAM dla LM Studio albo innego procesu, zatrzymaj serwis:

```bash
cd sam3_service
./stop.sh
```

Po restarcie serwera model zaladuje sie ponownie.
