# Third-party assets, models and licenses

The MIT license in `LICENSE` applies to the original code, configuration and
documentation in this repository unless a more specific notice says
otherwise. It does not relicense third-party code, downloaded checkpoints or
the example images in `asset_pipeline/sources/`.

## Runtime components

| Component | Used by | License / terms | Repository status |
| --- | --- | --- | --- |
| Practical-RIFE 4.25 | `frame_interpolation_service/` | [MIT](https://github.com/hzwer/Practical-RIFE/blob/main/LICENSE) | downloaded at setup time; no checkpoint is committed |
| SAM3 | `sam3_service/` | [SAM License](https://github.com/facebookresearch/sam3/blob/main/LICENSE) | optional external runtime/checkpoint; not committed |
| Ultralytics / YOLO | optional `yolo26` provider | [AGPL-3.0 or commercial Enterprise terms](https://github.com/ultralytics/ultralytics/blob/main/LICENSE) | installed only in the SAM3 environment; check terms for the intended distribution |
| ViTMatte `hustvl/vitmatte-small-composition-1k` | optional `vitmatte` provider | [Apache-2.0](https://huggingface.co/hustvl/vitmatte-small-composition-1k) | downloaded from Hugging Face when configured; not committed |
| Ultralytics CLIP | SAM3 text-prompt support | upstream Ultralytics repository terms | installed from the Git dependency in `sam3_service/requirements.txt` |

The Python requirements also install common libraries such as FastAPI,
Uvicorn, Pillow, NumPy, OpenCV, PyTorch, Transformers, `rembg`, ONNX Runtime,
`aura-sr`, `openai` and `gdown`. Their individual license texts are supplied
by their respective distributions and should be included in a release
bundle's dependency inventory.

## Example images

The files under `asset_pipeline/sources/` are project demonstration inputs,
not source code. Their generation/source history is documented in
[`asset_pipeline/sources/README.md`](asset_pipeline/sources/README.md), and the
repository owner confirms that they may be included in this public repository.
The MIT license for the original code does not apply to these images unless
stated separately.

## Model checkpoints

No model checkpoint is intended to be part of this repository. Setup scripts
download or load checkpoints into ignored runtime directories. A user who
publishes a bundle must provide the applicable upstream license alongside each
checkpoint and must not assume that the repository's MIT license covers it.

This file is an engineering inventory, not legal advice. Recheck upstream
terms before redistribution because model and dependency licenses can change.
