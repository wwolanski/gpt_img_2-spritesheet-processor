from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.rife_runtime import RifeRuntime, interpolate_sprite, load_runtime
from app.schemas import HealthResponse, InterpolationRequest, InterpolationResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)

runtime: RifeRuntime | None = None
LOGGER = logging.getLogger("frame_interpolation_service")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global runtime
    runtime = load_runtime()
    yield
    runtime = None


app = FastAPI(title="Sprite Frame Interpolation Service", version="1", lifespan=lifespan)


@app.get("/health")
async def health() -> HealthResponse:
    active = runtime or load_runtime()
    return HealthResponse(
        status="degraded" if active.warnings else "ok",
        model=str(active.model_path),
        device=active.device,
        half=active.half,
        warnings=active.warnings,
    )


@app.post("/v1/sprite/interpolate", response_model=InterpolationResponse)
async def interpolate(request: InterpolationRequest) -> InterpolationResponse:
    active = runtime or load_runtime()
    try:
        return interpolate_sprite(active, request)
    except RuntimeError as error:
        LOGGER.exception("RIFE interpolation failed")
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        LOGGER.warning("RIFE request rejected: %s", error)
        raise HTTPException(status_code=422, detail=str(error)) from error
