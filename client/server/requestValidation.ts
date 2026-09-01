import type { InlinePreviewFiles, JsonObject } from "../src/types/apiContract";
import { API_DEFAULT_LIMITS, SOURCE_NAME_PATTERN, SUPPORTED_IMAGE_EXTENSIONS } from "../src/types/apiContract";

export class HttpError extends Error {
  constructor(
    public readonly statusCode: number,
    message: string,
    public readonly code = "bad_request",
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "HttpError";
  }
}

export const MAX_REQUEST_BODY_BYTES = envLimit(
  "ASSET_PIPELINE_MAX_REQUEST_BODY_BYTES",
  API_DEFAULT_LIMITS.maxRequestBodyBytes,
);
export const MAX_SOURCES = envLimit("ASSET_PIPELINE_MAX_SOURCES", API_DEFAULT_LIMITS.maxSources);
export const MAX_WORKERS = envLimit("ASSET_PIPELINE_MAX_WORKERS", API_DEFAULT_LIMITS.maxWorkers);
export const MAX_PIPELINES = envLimit("ASSET_PIPELINE_MAX_PIPELINES", API_DEFAULT_LIMITS.maxPipelines);

export function requireString(value: unknown, field: string, maxLength = 256): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new HttpError(422, `Field '${field}' must be a non-empty string.`, "invalid_field");
  }
  if (value.length > maxLength) {
    throw new HttpError(422, `Field '${field}' is too long (max ${maxLength} characters).`, "invalid_field");
  }
  return value;
}

export function requireObject(value: unknown, field: string): JsonObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new HttpError(422, `Field '${field}' must be an object.`, "invalid_field");
  }
  return value;
}

export function decodePathComponent(value: string, field: string): string {
  try {
    return decodeURIComponent(value);
  } catch (error) {
    throw new HttpError(400, `Invalid encoded ${field}: ${String(error)}`, "invalid_path");
  }
}

export function requireSourceName(value: unknown): string {
  const source = requireString(value, "source", 255);
  if (
    !SOURCE_NAME_PATTERN.test(source) ||
    !SUPPORTED_IMAGE_EXTENSIONS.some((extension) => source.toLowerCase().endsWith(extension))
  ) {
    throw new HttpError(422, "source must be a supported image filename, not a path.", "invalid_source");
  }
  return source;
}

export function requireSourceNames(value: unknown): string[] {
  if (!Array.isArray(value)) {
    throw new HttpError(422, "sources must be an array.", "invalid_sources");
  }
  if (value.length < 1 || value.length > MAX_SOURCES) {
    throw new HttpError(422, `sources must contain between 1 and ${MAX_SOURCES} items.`, "invalid_sources");
  }
  const sources = value.map(requireSourceName);
  if (new Set(sources).size !== sources.length) {
    throw new HttpError(422, "sources cannot contain duplicates.", "invalid_sources");
  }
  return sources;
}

export function requireWorkers(value: unknown): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 1 || value > MAX_WORKERS) {
    throw new HttpError(422, `workers must be an integer between 1 and ${MAX_WORKERS}.`, "invalid_workers");
  }
  return value;
}

export function validatePipelineId(value: unknown): void {
  if (value !== undefined && (typeof value !== "string" || value.trim().length === 0 || value.length > 120)) {
    throw new HttpError(422, "pipelineId must be a non-empty string.", "invalid_pipeline");
  }
}

export function validatePipelineIds(value: unknown): void {
  if (value === undefined) return;
  if (
    !Array.isArray(value) ||
    value.length > MAX_PIPELINES ||
    value.some((item) => typeof item !== "string" || item.trim().length === 0)
  ) {
    throw new HttpError(
      422,
      `pipelineIds must contain at most ${MAX_PIPELINES} non-empty strings.`,
      "invalid_pipelines",
    );
  }
  if (new Set(value).size !== value.length) {
    throw new HttpError(422, "pipelineIds cannot contain duplicates.", "invalid_pipelines");
  }
}

export function isJsonObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isInlinePreviewFiles(value: unknown): value is InlinePreviewFiles {
  if (!isJsonObject(value)) {
    return false;
  }
  return Object.values(value).every((item) => typeof item === "string");
}

export function envLimit(name: string, fallback: number): number {
  const value = Number(process.env[name] ?? fallback);
  return Number.isInteger(value) && value > 0 ? value : fallback;
}
