import type { ControlsState } from "./pipeline";
import type { SemanticMetadata, SemanticDebugMetadata, SemanticEditorPreset } from "./semantic";
export type {
  ApiError,
  ApiErrorPayload,
  CompareMatrixRequest,
  CompareRequest,
  ExportRequest,
  InlinePreviewFiles,
  JsonObject,
  JsonValue,
  PipelineOptions,
  ProcessRequest,
  SemanticPresetWriteRequest,
} from "./apiContract";

export type PipelineSpec = {
  id: string;
  enabled: boolean;
  label: string;
  description: string;
  profile_hint: string;
  stages: PipelineStageSpec[];
  optionOverrides: Record<string, number | string | boolean>;
  optional?: string;
};

export type PipelineStageSpec = {
  id: string;
  included: boolean;
};

export type StageRegistryItem = {
  id: string;
  label: string;
  description: string;
  configurable: boolean;
};

export type DescribeResponse = {
  defaults: Record<string, number | string | boolean>;
  pipelines: PipelineSpec[];
  profiles: string[];
  profilePresets: Record<string, Partial<Record<keyof ControlsState, number | string | boolean>>>;
  stageRegistry: StageRegistryItem[];
  capabilities: {
    rembg: boolean;
    auraSr: boolean;
    sam3: boolean;
    rife: boolean;
    workers: number;
    semanticMaskModels?: string[];
  };
  paths: {
    sources: string;
    publicAssets: string;
  };
};

export type SourceItem = {
  name: string;
  width: number;
  height: number;
  bytes: number;
};

export type SourcesResponse = {
  sources: SourceItem[];
};

export type FrameMetadata = {
  index: number;
  sourceBox: { x: number; y: number; width: number; height: number };
  sheetBox: { x: number; y: number; width: number; height: number };
};

export type ResolutionContract = {
  semanticCoordinateSpace: string;
  outputCoordinateSpace: string;
  upscaleMode: string;
  outputScale: { x: number; y: number };
  semanticInputSize?: {
    coordinateSpace: string;
    width: number;
    height: number;
  };
  preUpscaleProcessedSize?: { width: number; height: number };
  preUpscaleNormalizedFrameSize?: { width: number; height: number };
  preUpscaleSheetSize?: { width: number; height: number };
};

export type ProcessResponse = {
  source: string;
  previewId: string;
  pipelineId: string;
  pipelineStages: Record<string, boolean>;
  profile: string;
  keyColor: { r: number; g: number; b: number };
  sourceSize?: { width: number; height: number };
  processedSize?: { width: number; height: number };
  resolutionContract?: ResolutionContract;
  normalizedFrameSize: { width: number; height: number };
  frames: FrameMetadata[];
  semantic?: SemanticMetadata;
  semanticDebug?: SemanticDebugMetadata;
  stabilization?: Record<string, unknown>;
  metrics: {
    score: number;
    border_leak_ratio: number;
    green_spill_ratio: number;
    edge_alpha_ratio: number;
    tiny_component_count: number;
    component_count: number;
    opaque_coverage: number;
  };
  previewFiles: {
    processed: string;
    alpha: string;
    sheet: string;
    metadata: string;
  };
  durationMs?: number;
};

export type CompareResponse = {
  source: string | null;
  sources: string[];
  batchId: string;
  workers: number;
  durationMs: number;
  results: ProcessResponse[];
};

export type ExportResponse = {
  target: string;
  previewId: string;
  copiedFiles: string[];
  publicPath: string;
};

export type SemanticPresetsResponse = {
  presets: SemanticEditorPreset[];
};

export type SaveSemanticPresetResponse = {
  preset: SemanticEditorPreset;
  presets: SemanticEditorPreset[];
};

export type DeleteSemanticPresetResponse = {
  deleted: string;
  presets: SemanticEditorPreset[];
};
