import { apiClient } from "./client";
import type {
  DescribeResponse,
  SourcesResponse,
  ProcessResponse,
  CompareResponse,
  ExportResponse,
  SemanticPresetsResponse,
  SaveSemanticPresetResponse,
  DeleteSemanticPresetResponse,
  SemanticEditorPresetSettings,
} from "../types/pipeline";
import type {
  CompareMatrixRequest,
  CompareRequest,
  ExportRequest,
  PipelineOptions,
  ProcessRequest,
  SemanticPresetWriteRequest,
} from "../types/apiContract";

export function fetchDescribe(): Promise<DescribeResponse> {
  return apiClient.get("/describe").then((r) => r.data);
}

export function fetchSources(): Promise<SourcesResponse> {
  return apiClient.get("/sources").then((r) => r.data);
}

export function processSource(
  source: string,
  pipelineId: string,
  options: PipelineOptions,
  signal?: AbortSignal,
): Promise<ProcessResponse> {
  const request: ProcessRequest = { source, pipelineId, options };
  return apiClient.post("/process", request, { signal }).then((r) => r.data);
}

export function comparePipelines(
  source: string,
  pipelineIds: string[],
  workers: number,
  options: PipelineOptions,
  signal?: AbortSignal,
): Promise<CompareResponse> {
  const request: CompareRequest = { source, pipelineIds, workers, options };
  return apiClient.post("/compare", request, { signal }).then((r) => r.data);
}

export function compareAllSources(
  sources: string[],
  pipelineIds: string[],
  workers: number,
  options: PipelineOptions,
  signal?: AbortSignal,
): Promise<CompareResponse> {
  const request: CompareMatrixRequest = { sources, pipelineIds, workers, options };
  return apiClient.post("/compare-matrix", request, { signal }).then((r) => r.data);
}

export function exportPreview(previewId: string, targetName: string): Promise<ExportResponse> {
  const request: ExportRequest = { previewId, targetName, overwrite: true };
  return apiClient.post("/export", request).then((r) => r.data);
}

export function fetchSemanticPresets(): Promise<SemanticPresetsResponse> {
  return apiClient.get("/semantic-presets").then((r) => r.data);
}

export function saveSemanticPreset(
  name: string,
  settings: SemanticEditorPresetSettings,
): Promise<SaveSemanticPresetResponse> {
  const request: SemanticPresetWriteRequest = { name, settings };
  return apiClient.post("/semantic-presets", request).then((r) => r.data);
}

export function deleteSemanticPreset(name: string): Promise<DeleteSemanticPresetResponse> {
  return apiClient.delete(`/semantic-presets/${encodeURIComponent(name)}`).then((r) => r.data);
}
