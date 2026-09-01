# Frame Interpolation Service

Long-lived FastAPI service for 2x sprite interpolation. Runtime uses Practical-RIFE 4.25 because its anime/line-art tuning fits outlined 2D sprites better than natural-video FILM models.

## Model

`setup_venv.sh` downloads a pinned Practical-RIFE runtime and the Practical-RIFE 4.25 bundle linked by upstream. Model lands under `models/Practical-RIFE/train_log/`. The runtime commit can be overridden with `RIFE_REPOSITORY_REF`; the downloaded archive is always verified against the SHA-256 pinned in `download_model.sh` before extraction.

```text
RIFE_HDv3.py
IFNet_HDv3.py
flownet.pkl
```

Upstream: <https://github.com/hzwer/Practical-RIFE>. Model and code use MIT license.

## Run

```bash
cd frame_interpolation_service
./setup_venv.sh
./install_service.sh
curl http://127.0.0.1:8775/health
```

CPU debug:

```bash
RIFE_DEVICE=cpu RIFE_HALF=0 ./start.sh
```

`RIFE_HALF=0` is default. Practical-RIFE 4.25 creates selected internal tensors in FP32, so forced FP16 is unsafe without patching upstream model code. Small sprite frames do not justify that compatibility risk.

Service accepts 2-16 normalized RGBA PNG frames. Default loop mode inserts one midpoint after every source frame, including last-to-first: 8 frames become 16, 16 become 32. RGB is inferred over neutral gray matte. Alpha gets separate RIFE inference, preventing opaque ghost rectangles around sprites.

Pipeline URL override:

```bash
ASSET_PIPELINE_INTERPOLATION_URL=http://127.0.0.1:8775
```
