import type { ApiErrorPayload } from "../src/types/apiContract";
import { HttpError } from "./requestValidation";

export function apiErrorPayload(error: unknown): ApiErrorPayload {
  if (error instanceof HttpError) {
    const details = Object.keys(error.details).length ? { details: error.details } : {};
    return { ok: false, error: { code: error.code, message: error.message, ...details } };
  }
  if (error instanceof Error && (error as Error & { code?: string }).code === "ENOENT") {
    return { ok: false, error: { code: "not_found", message: "Requested resource was not found." } };
  }
  return { ok: false, error: { code: "internal_error", message: "Internal asset pipeline error." } };
}
