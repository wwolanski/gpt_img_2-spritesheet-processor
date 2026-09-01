export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = Record<string, unknown>;

export const API_DEFAULT_LIMITS = {
  maxRequestBodyBytes: 4 * 1024 * 1024,
  maxSources: 32,
  maxWorkers: 16,
  maxPipelines: 16,
} as const;

export const SOURCE_NAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,254}$/;
export const SUPPORTED_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"] as const;

export type PipelineOptions = JsonObject;

export type ProcessRequest = {
  source: string;
  pipelineId?: string;
  options: PipelineOptions;
};

export type CompareRequest = {
  source: string;
  pipelineIds?: string[];
  workers: number;
  options: PipelineOptions;
};

export type CompareMatrixRequest = {
  sources?: string[];
  pipelineIds?: string[];
  workers: number;
  options: PipelineOptions;
};

export type ExportRequest = {
  previewId: string;
  targetName: string;
  overwrite?: boolean;
};

export type SemanticPresetWriteRequest = {
  name: string;
  settings: JsonObject;
};

export type ApiError = {
  code: string;
  message: string;
  details?: Record<string, unknown>;
};

export type ApiErrorPayload = {
  ok: false;
  error: ApiError;
};

export type InlinePreviewFiles = Record<string, string>;
