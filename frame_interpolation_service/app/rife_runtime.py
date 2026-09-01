from __future__ import annotations

import base64
from dataclasses import dataclass, field
from io import BytesIO
import logging
import os
from pathlib import Path
import sys
import importlib
from threading import Lock

import numpy as np
from PIL import Image

from app.schemas import InterpolatedFrame, InterpolationRequest, InterpolationResponse

LOGGER = logging.getLogger("frame_interpolation_service")


@dataclass
class RifeRuntime:
    model_path: Path
    device: str
    half: bool
    model: object | None = None
    warnings: list[str] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)


def default_model_path() -> Path:
    default = Path(__file__).resolve().parents[1] / "models" / "Practical-RIFE" / "train_log"
    return Path(os.environ.get("RIFE_MODEL_PATH", default)).resolve()


def load_runtime() -> RifeRuntime:
    device = os.environ.get("RIFE_DEVICE", "cuda").strip() or "cuda"
    half = os.environ.get("RIFE_HALF", "0") == "1" and device != "cpu"
    runtime = RifeRuntime(default_model_path(), device, half)
    try:
        import torch

        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        model_dir = runtime.model_path
        model_module = model_dir / "RIFE_HDv3.py"
        model_network = model_dir / "IFNet_HDv3.py"
        weights = model_dir / "flownet.pkl"
        repo_dir = model_dir.parent
        if not model_module.is_file() or not model_network.is_file() or not weights.is_file():
            raise FileNotFoundError(
                f"RIFE 4.25 files missing in {model_dir}; " "expected RIFE_HDv3.py, IFNet_HDv3.py and flownet.pkl"
            )
        if not (repo_dir / "model" / "warplayer.py").is_file():
            raise FileNotFoundError(f"Practical-RIFE runtime sources missing in {repo_dir}")
        sys.path.insert(0, str(repo_dir))
        try:
            Model = importlib.import_module("train_log.RIFE_HDv3").Model
        finally:
            sys.path.pop(0)
        model = Model()
        model.load_model(str(model_dir), -1)
        model.eval()
        model.device()
        if half and hasattr(model, "flownet"):
            model.flownet.half()
        runtime.model = model
        LOGGER.info("RIFE runtime ready: model=%s device=%s half=%s", model_dir, device, half)
    except Exception as error:  # pragma: no cover - depends on external runtime.
        runtime.warnings.append(f"RIFE runtime unavailable: {error}")
        LOGGER.warning(runtime.warnings[-1])
    return runtime


def decode_rgba(encoded: str) -> np.ndarray:
    image = Image.open(BytesIO(base64.b64decode(encoded))).convert("RGBA")
    return np.asarray(image, dtype=np.uint8)


def encode_rgba(image: np.ndarray) -> str:
    output = BytesIO()
    Image.fromarray(image.astype(np.uint8), mode="RGBA").save(output, format="PNG", compress_level=1)
    return base64.b64encode(output.getvalue()).decode("ascii")


def composite_matte(rgba: np.ndarray, matte_color: tuple[int, int, int]) -> np.ndarray:
    alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
    matte = np.asarray(matte_color, dtype=np.float32).reshape(1, 1, 3)
    return np.clip(rgba[:, :, :3].astype(np.float32) * alpha + matte * (1.0 - alpha), 0, 255).astype(np.uint8)


def torch_frame(rgb: np.ndarray, device: str, half: bool) -> object:
    import torch

    tensor = torch.from_numpy(np.ascontiguousarray(rgb.transpose(2, 0, 1))).unsqueeze(0).float().div_(255.0)
    tensor = tensor.to(device)
    return tensor.half() if half else tensor


def pad_tensor(tensor: object, multiple: int = 128) -> tuple[object, int, int]:
    import torch.nn.functional as functional

    height, width = int(tensor.shape[-2]), int(tensor.shape[-1])
    pad_h = (multiple - height % multiple) % multiple
    pad_w = (multiple - width % multiple) % multiple
    return functional.pad(tensor, (0, pad_w, 0, pad_h), mode="replicate"), height, width


def infer_rgb(runtime: RifeRuntime, left: np.ndarray, right: np.ndarray, scale: float) -> np.ndarray:
    if runtime.model is None:
        raise RuntimeError((runtime.warnings or ["RIFE runtime unavailable"])[0])
    import torch

    left_tensor, height, width = pad_tensor(torch_frame(left, runtime.device, runtime.half))
    right_tensor, _, _ = pad_tensor(torch_frame(right, runtime.device, runtime.half))
    # Practical-RIFE updates internal warp-grid caches in place. PyTorch 2.12
    # forbids that under inference_mode; no_grad keeps inference correct.
    with torch.no_grad():
        output = runtime.model.inference(left_tensor, right_tensor, scale=scale)
    result = output[0, :, :height, :width].float().clamp_(0, 1).mul_(255).byte().cpu().numpy().transpose(1, 2, 0)
    return np.ascontiguousarray(result)


def interpolate_pair(
    runtime: RifeRuntime,
    left: np.ndarray,
    right: np.ndarray,
    matte_color: tuple[int, int, int],
    alpha_mode: str,
    scale: float,
) -> np.ndarray:
    rgb = infer_rgb(runtime, composite_matte(left, matte_color), composite_matte(right, matte_color), scale)
    if alpha_mode == "linear":
        alpha = np.rint((left[:, :, 3].astype(np.float32) + right[:, :, 3].astype(np.float32)) * 0.5).astype(np.uint8)
    else:
        left_alpha = np.repeat(left[:, :, 3:4], 3, axis=2)
        right_alpha = np.repeat(right[:, :, 3:4], 3, axis=2)
        alpha = infer_rgb(runtime, left_alpha, right_alpha, scale)[:, :, 0]
    rgba = np.dstack([rgb, alpha])
    rgba[alpha == 0, :3] = np.asarray(matte_color, dtype=np.uint8)
    return rgba


def interpolate_sprite(runtime: RifeRuntime, request: InterpolationRequest) -> InterpolationResponse:
    if runtime.model is None:
        raise RuntimeError((runtime.warnings or ["RIFE runtime unavailable"])[0])
    inputs = [decode_rgba(frame.rgbaPngBase64) for frame in request.frames]
    for spec, image in zip(request.frames, inputs):
        if image.shape[:2] != (spec.height, spec.width):
            raise ValueError(
                f"frame {spec.index} PNG size {image.shape[1]}x{image.shape[0]} "
                f"does not match declared {spec.width}x{spec.height}"
            )
    options = request.options
    pair_count = len(inputs) if options.loop else len(inputs) - 1
    output: list[InterpolatedFrame] = []
    with runtime.lock:
        for source_index, frame in enumerate(inputs):
            next_index = (source_index + 1) % len(inputs)
            output.append(
                InterpolatedFrame(
                    index=len(output),
                    sourceFrame=source_index,
                    nextSourceFrame=source_index,
                    interpolated=False,
                    rgbaPngBase64=encode_rgba(frame),
                )
            )
            if source_index < pair_count:
                midpoint = interpolate_pair(
                    runtime, frame, inputs[next_index], options.matteColor, options.alphaMode, options.scale
                )
                output.append(
                    InterpolatedFrame(
                        index=len(output),
                        sourceFrame=source_index,
                        nextSourceFrame=next_index,
                        interpolated=True,
                        rgbaPngBase64=encode_rgba(midpoint),
                    )
                )
    return InterpolationResponse(
        loop=options.loop,
        sourceFrameCount=len(inputs),
        outputFrameCount=len(output),
        frames=output,
    )
