import type {
  SemanticManualPart,
  SemanticEdit,
  SemanticEditorPart,
  SemanticEditTool,
  SemanticInputMode,
  SemanticGroundingProjectionMode,
} from "./semantic";
import type { ProcessResponse } from "./api";

export type OptionValue =
  number | string | boolean | Record<string, boolean> | SemanticManualPart[] | SemanticEditorPart[] | SemanticEdit[];

export type StageStatus = "idle" | "running" | "ready" | "error";

export type StageGroup = {
  id: string;
  label: string;
  description: string;
  included: boolean;
  configurable: boolean;
  fields: Array<keyof ControlsState>;
};

export type VariantPreview = {
  id: string;
  label: string;
  pipelineId: string;
  source: string;
  controls: ControlsState;
  result?: ProcessResponse;
  status: "ready" | "running" | "error";
  error?: string;
};

export type ControlsState = {
  source: string;
  profile: string;
  pipelineId: string;
  transparentThreshold: number;
  opaqueThreshold: number;
  edgeSoftness: number;
  edgeBlurSigma: number;
  despillStrength: number;
  despillAlphaMode: string;
  despillAlphaStrength: number;
  neutralizeEdges: string;
  neutralizeStrength: number;
  edgeDarken: number;
  outlineWidth: number;
  outlineOpacity: number;
  outlineBlur: number;
  alphaCleanupMinArea: number;
  alphaCleanupCloseSize: number;
  cropPadding: number;
  framePadding: number;
  minFrameArea: number;
  alphaCutoff: number;
  flowDeflickerStrength: number;
  flowDeflickerRadius: number;
  flowColorTolerance: number;
  flowAlphaTolerance: number;
  flowConsistencyTolerance: number;
  flowMaxDisplacement: number;
  flowConfidenceFloor: number;
  temporalDeflickerStrength: number;
  temporalStaticCoverage: number;
  temporalColorTolerance: number;
  temporalAlphaTolerance: number;
  sheetExtrudePixels: number;
  upscaleMode: string;
  pipelineStages: Record<string, boolean>;
  semanticManualParts: SemanticManualPart[];
  semanticEdits: SemanticEdit[];
  semanticEditorParts: SemanticEditorPart[];
  semanticEditTool: SemanticEditTool;
  semanticInputMode: SemanticInputMode;
  semanticGroundingMinConfidence: number;
  semanticGroundingAlphaCutoff: number;
  semanticGroundingDilationRadius: number;
  semanticGroundingAllowFrameReassign: boolean;
  semanticGroundingFrameMinScore: number;
  semanticGroundingProjectionMode: SemanticGroundingProjectionMode;
  semanticGroundingExpandRatio: number;
  semanticGroundingExpandMinPx: number;
  semanticGroundingEmitBbox: boolean;
  semanticGroundingEmitPositivePoint: boolean;
  semanticMaskModel: string;
  partStabilizeEnabled: boolean;
  partRepairEnabled: boolean;
  partRepairSearchScale: number;
  partPatchLockStrength: number;
  partMedianStrength: number;
  exportSlug: string;
};

export type {
  SemanticManualPart,
  SemanticEdit,
  SemanticEditTool,
  SemanticInputMode,
  SemanticGroundingProjectionMode,
  SemanticEditorPart,
  SemanticEditorPreset,
  SemanticEditorPresetSettings,
  SemanticPart,
  SemanticGrounding,
  SemanticDebugPartSpec,
  SemanticDebugTrack,
  SemanticMetadata,
  SemanticIssue,
  SemanticDebugFrame,
  SemanticDebugMetadata,
} from "./semantic";

export type {
  DescribeResponse,
  SourceItem,
  SourcesResponse,
  ProcessResponse,
  CompareResponse,
  ExportResponse,
  SemanticPresetsResponse,
  SaveSemanticPresetResponse,
  DeleteSemanticPresetResponse,
  PipelineSpec,
  PipelineStageSpec,
  StageRegistryItem,
  FrameMetadata,
} from "./api";
