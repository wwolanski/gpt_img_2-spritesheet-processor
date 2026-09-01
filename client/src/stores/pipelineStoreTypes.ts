import type {
  ControlsState,
  DescribeResponse,
  ProcessResponse,
  SourceItem,
  StageStatus,
  VariantPreview,
  SemanticEdit,
  SemanticEditTool,
  SemanticEditorPart,
  SemanticEditorPresetSettings,
  SemanticManualPart,
} from "../types/pipeline";

export type PipelineState = {
  config: DescribeResponse | undefined;
  sources: SourceItem[];
  controls: ControlsState;
  pipelineTweaks: Record<string, Partial<ControlsState>>;
  variants: VariantPreview[];
  activeVariantId: string | null;
  current: ProcessResponse | undefined;
  activeStageId: string | null;
  stageStatuses: Record<string, StageStatus>;
  status: string;
  exportStatus: string;
  loading: boolean;
  showBoxes: boolean;
  showParts: boolean;
  activePartId: string | null;
  activeEditId: string | null;
  animBg: string;
  autoRunTrigger: number;
  autoRunEnabled: boolean;
  animPlaying: boolean;
  enabledFrames: Set<number>;
  gamepadActive: boolean;
  animFps: number;
  moveSpeed: number;
  processedImage: HTMLImageElement | undefined;
  sheetImage: HTMLImageElement | undefined;

  /* ─── Init ─── */
  initConfig: (config: DescribeResponse, firstSource: string) => void;
  setSources: (sources: SourceItem[]) => void;

  /* ─── Controls ─── */
  setControl: <Key extends keyof ControlsState>(field: Key, value: ControlsState[Key]) => void;

  /* ─── Pipeline sync ─── */
  saveTweak: (field: keyof ControlsState) => void;

  /* ─── UI state ─── */
  setActiveStageId: (id: string | null) => void;
  setShowBoxes: (v: boolean) => void;
  setShowParts: (v: boolean) => void;
  setActivePartId: (id: string | null) => void;
  setActiveEditId: (id: string | null) => void;
  setAnimBg: (v: string) => void;
  setAnimPlaying: (v: boolean) => void;
  toggleFrame: (frameIndex: number) => void;
  resetEnabledFrames: (indexes: number[]) => void;
  setGamepadActive: (v: boolean) => void;
  setAnimFps: (v: number) => void;
  setMoveSpeed: (v: number) => void;
  setStatus: (v: string) => void;
  setExportStatus: (v: string) => void;
  setLoading: (v: boolean) => void;
  setCurrent: (result: ProcessResponse, label: string, ctrlOverride?: ControlsState) => void;
  setSemanticEditTool: (tool: SemanticEditTool) => void;
  addSemanticEdit: (edit: SemanticEdit) => void;
  clearSemanticEdits: () => void;
  setSemanticManualParts: (parts: SemanticManualPart[]) => void;
  setSemanticEditorParts: (parts: SemanticEditorPart[]) => void;
  clearSemanticEditorPartsOverride: () => void;
  applySemanticPreset: (preset: SemanticEditorPresetSettings) => void;
  setVariants: (v: VariantPreview[]) => void;
  upsertRunningVariant: (pipelineId: string, source: string, ctrl: ControlsState) => void;
  markVariantError: (pipelineId: string, source: string, error: unknown) => void;
  setStageStatuses: (status: StageStatus) => void;
  setPreviewImages: (processedImage?: HTMLImageElement, sheetImage?: HTMLImageElement) => void;
  setAutoRunEnabled: (v: boolean) => void;
};
