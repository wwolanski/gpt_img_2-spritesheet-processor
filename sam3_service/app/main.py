from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from threading import Lock

from fastapi import FastAPI

from app.sam3_service import (
    SUPPORTED_MASK_MODELS,
    Sam3Runtime,
    default_mask_model,
    load_runtime,
    normalize_mask_model,
    segment_sprite,
    unload_runtime,
)
from app.schemas import HealthResponse, SegmentRequest, SegmentResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
LOGGER = logging.getLogger("sam3_service")

active_runtime: Sam3Runtime | None = None
runtime_lock = Lock()


def get_runtime(mask_model: str | None = None) -> Sam3Runtime:
    global active_runtime
    name = normalize_mask_model(mask_model or default_mask_model())
    with runtime_lock:
        if active_runtime is not None and active_runtime.name == name:
            LOGGER.info("runtime reuse: mask_model=%s path=%s", active_runtime.name, active_runtime.model_path)
            return active_runtime
        if active_runtime is not None:
            LOGGER.info("runtime switch: from=%s to=%s", active_runtime.name, name)
            unload_runtime(active_runtime)
        active_runtime = load_runtime(name)
        return active_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    global active_runtime
    LOGGER.info("service startup: default_mask_model=%s", default_mask_model())
    get_runtime(default_mask_model())
    yield
    LOGGER.info("service shutdown")
    with runtime_lock:
        unload_runtime(active_runtime)
        active_runtime = None


app = FastAPI(title="Asset Pipeline Semantic Service", version="1", lifespan=lifespan)


@app.get("/health")
async def health() -> HealthResponse:
    active = active_runtime or get_runtime(default_mask_model())
    warnings = list(active.warnings or [])
    return HealthResponse(
        status="degraded" if warnings else "ok",
        provider=active.provider,
        model=active.model_path,
        maskModel=active.name,
        device=active.device,
        half=active.half,
        version="1",
        models=list(SUPPORTED_MASK_MODELS),
        warnings=warnings,
    )


@app.post("/v1/sprite/segment")
async def segment(request: SegmentRequest) -> SegmentResponse:
    LOGGER.info(
        "http segment received: requested_mask_model=%s frames=%s parts=%s",
        request.options.maskModel,
        len(request.frames),
        len(request.parts),
    )
    active = get_runtime(request.options.maskModel)
    response = SegmentResponse(parts=segment_sprite(active, request))
    LOGGER.info("http segment response ready: mask_model=%s parts=%s", active.name, len(response.parts))
    return response
