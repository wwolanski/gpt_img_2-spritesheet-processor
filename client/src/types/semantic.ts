export type SemanticManualPart = {
  id: string;
  label: string;
  prompt: string;
  mobility: "static" | "low" | "medium" | "high" | "accessory";
  persistence: "always" | "occasional";
};

export type SemanticEdit = {
  frame: number;
  partId: string;
  type: "positive_point" | "negative_point" | "bbox";
  x?: number;
  y?: number;
  box?: number[];
  x0?: number;
  y0?: number;
  x1?: number;
  y1?: number;
  space?: {
    coordinateSpace: string;
    frameWidth: number;
    frameHeight: number;
    sourceWidth?: number;
    sourceHeight?: number;
    offsetX?: number;
    offsetY?: number;
    previewId?: string;
    frameCount?: number;
    frameInterpolationFactor?: number;
  };
};

export type SemanticEditTool = "positive_point" | "negative_point";
export type SemanticInputMode = "neutral_matte" | "raw_greenscreen" | "final_processed";
export type SemanticGroundingProjectionMode = "by_persistence" | "source_only" | "all_frames";

export type SemanticEditorPart = SemanticManualPart & {
  color?: string;
  stabilizeSettings?: SemanticPartStabilizeSettings;
  edits: SemanticEdit[];
};

export type SemanticPartStabilizeSettings = {
  enabled?: boolean;
  repairEnabled?: boolean;
  repairSearchScale?: number;
  patchLockStrength?: number;
  medianStrength?: number;
};

export type SemanticEditorPresetSettings = {
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
  semanticEditorParts: SemanticEditorPart[];
};

export type SemanticEditorPreset = {
  name: string;
  updatedAt: string;
  settings: SemanticEditorPresetSettings;
};

export type SemanticPart = {
  id: string;
  label: string;
  color: string;
  mobility: "static" | "low" | "medium" | "high" | "accessory";
  persistence: "always" | "occasional";
  confidence: number;
  presence: boolean[];
  warnings: string[];
  maskStatuses?: string[];
  frameMetrics?: SemanticFrameMetric[];
  trackSummary?: SemanticTrackSummary;
  stabilizeSettings?: SemanticPartStabilizeSettings;
  masks?: string[];
  boxes: Array<{
    index: number;
    x: number;
    y: number;
    width: number;
    height: number;
    area: number;
    center_x: number;
    center_y: number;
  } | null>;
};

export type SemanticFrameMetric = {
  frame: number;
  status?: string;
  area?: number;
  areaRatio?: number;
  silhouetteRatio?: number;
  centerX?: number;
  centerY?: number;
  centerDistance?: number;
  componentCount?: number;
  iouPrev?: number;
  [key: string]: unknown;
};

export type SemanticTrackSummary = {
  accepted: number;
  repaired: number;
  missing: number;
  rejected: number;
  areaJitter: number;
  centroidJitter: number;
  loopIoU: number;
};

export type SemanticGrounding = {
  frame: number;
  bbox_2d: [number, number, number, number];
  point_2d: [number, number];
  confidence: number;
};

export type SemanticDebugPartSpec = SemanticManualPart & {
  grounding?: SemanticGrounding[];
};

export type SemanticDebugTrack = {
  id: string;
  label: string;
  color: string;
  confidence: number;
  presence: boolean[];
  warnings: string[];
  maskStatuses?: string[];
  frameMetrics?: SemanticFrameMetric[];
  trackSummary?: SemanticTrackSummary;
  stabilizeSettings?: SemanticPartStabilizeSettings;
  boxes: SemanticPart["boxes"];
  masks: string[];
};

export type SemanticMetadata = {
  enabled: boolean;
  sam3Url: string;
  maskModel?: string;
  vlmBaseUrl: string;
  warnings: string[];
  semanticIssues: SemanticIssue[];
  parts: SemanticPart[];
  metrics: {
    part_presence_failures: number;
    part_area_jitter: number;
    part_centroid_jitter: number;
    part_edge_jitter: number;
    semantic_confidence_min: number;
    manual_review_required: boolean;
  };
};

export type SemanticIssue = {
  partId?: string;
  frame?: number;
  type: string;
  severity: "info" | "warn" | "review";
  source: string;
  message: string;
};

export type SemanticDebugFrame = {
  index: number;
  width: number;
  height: number;
  sourceWidth?: number;
  sourceHeight?: number;
  semanticOffset?: { x: number; y: number };
  files: {
    rawRgb: string;
    baseAlpha: string;
    samRgb: string;
    finalRgba: string;
  };
};

export type SemanticDebugMetadata = {
  inputMode: SemanticInputMode;
  stageEnabled: boolean;
  frames: SemanticDebugFrame[];
  resolutionContract?: {
    coordinateSpace: string;
    upscaleMode: string;
    outputScale: { x: number; y: number };
    note?: string;
  };
  partSpecs: SemanticDebugPartSpec[];
  qwenGrounding?: SemanticDebugPartSpec[];
  frameInterpolation?: {
    enabled: boolean;
    status: string;
    factor: number;
    loop?: boolean;
    sourceFrameCount?: number;
    outputFrameCount?: number;
    model?: string;
    error?: string | null;
  };
  groundingStage?: {
    enabled: boolean;
    edits: SemanticEdit[];
    settings: Record<string, unknown> | null;
    warnings: string[];
    audit: Record<string, unknown>;
  };
  groundingEdits?: SemanticEdit[];
  sam3Edits?: SemanticEdit[];
  manualEdits: SemanticEdit[];
  sam3RawParts?: SemanticDebugTrack[];
  sam3ValidatedParts?: SemanticDebugTrack[];
  audit: Record<string, unknown>;
};
