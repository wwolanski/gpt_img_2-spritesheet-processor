from __future__ import annotations

from typing import Mapping

from asset_pipeline.services.contracts import JsonObject, JsonValue


class AssetPipelineError(Exception):
    """Expected, serializable error at the pipeline boundary."""

    default_code = "pipeline_error"
    default_status_code = 500

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Mapping[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.status_code = status_code or self.default_status_code
        self.details = dict(details or {})

    def payload(self) -> JsonObject:
        error: JsonObject = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return {"ok": False, "error": error}


class ValidationError(AssetPipelineError, ValueError):
    default_code = "invalid_request"
    default_status_code = 422


class ConfigValidationError(AssetPipelineError):
    default_code = "invalid_config"
    default_status_code = 500


def error_payload(error: BaseException) -> tuple[int, JsonObject]:
    if isinstance(error, AssetPipelineError):
        return error.status_code, error.payload()
    if isinstance(error, FileNotFoundError):
        return 404, AssetPipelineError(str(error), code="not_found", status_code=404).payload()
    if isinstance(error, (TypeError, ValueError, KeyError)):
        return 422, ValidationError(str(error)).payload()
    return 500, AssetPipelineError("Internal pipeline error.", code="internal_error", status_code=500).payload()
