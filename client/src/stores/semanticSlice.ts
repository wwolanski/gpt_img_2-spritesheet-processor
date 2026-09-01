import type { PipelineState } from "./pipelineStoreTypes";
import { semanticPresetTweak } from "../utils/semanticEditor";

type PipelineStateSetter = (
  partial: Partial<PipelineState> | ((state: PipelineState) => Partial<PipelineState>),
) => void;

export type SemanticSlice = Pick<
  PipelineState,
  | "setSemanticEditTool"
  | "addSemanticEdit"
  | "clearSemanticEdits"
  | "setSemanticManualParts"
  | "setSemanticEditorParts"
  | "clearSemanticEditorPartsOverride"
  | "applySemanticPreset"
>;

export const createSemanticActions = (set: PipelineStateSetter, get: () => PipelineState): SemanticSlice => ({
  setSemanticEditTool: (semanticEditTool) =>
    set((state) => ({
      controls: { ...state.controls, semanticEditTool },
    })),

  addSemanticEdit: (edit) => {
    const state = get();
    const pipelineId = state.controls.pipelineId;
    const semanticEdits = [...state.controls.semanticEdits, edit];
    const controls = { ...state.controls, semanticEdits };
    set({
      controls,
      pipelineTweaks: {
        ...state.pipelineTweaks,
        [pipelineId]: { ...state.pipelineTweaks[pipelineId], semanticEdits },
      },
      autoRunTrigger: state.autoRunTrigger + 1,
    });
  },

  clearSemanticEdits: () => {
    const state = get();
    const pipelineId = state.controls.pipelineId;
    const controls = { ...state.controls, semanticEdits: [] };
    set({
      controls,
      pipelineTweaks: {
        ...state.pipelineTweaks,
        [pipelineId]: { ...state.pipelineTweaks[pipelineId], semanticEdits: [] },
      },
      autoRunTrigger: state.autoRunTrigger + 1,
    });
  },

  setSemanticManualParts: (semanticManualParts) => {
    const state = get();
    const pipelineId = state.controls.pipelineId;
    const controls = { ...state.controls, semanticManualParts };
    set({
      controls,
      pipelineTweaks: {
        ...state.pipelineTweaks,
        [pipelineId]: { ...state.pipelineTweaks[pipelineId], semanticManualParts },
      },
      autoRunTrigger: state.autoRunTrigger + 1,
    });
  },

  setSemanticEditorParts: (semanticEditorParts) => {
    const state = get();
    const pipelineId = state.controls.pipelineId;
    const controls = { ...state.controls, semanticEditorParts };
    set({
      controls,
      pipelineTweaks: {
        ...state.pipelineTweaks,
        [pipelineId]: { ...state.pipelineTweaks[pipelineId], semanticEditorParts },
      },
      autoRunTrigger: state.autoRunTrigger + 1,
    });
  },

  clearSemanticEditorPartsOverride: () => {
    const state = get();
    const pipelineId = state.controls.pipelineId;
    const currentTweak = state.pipelineTweaks[pipelineId] ?? {};
    const { semanticEditorParts: _semanticEditorParts, ...restTweak } = currentTweak;
    set({
      controls: { ...state.controls, semanticEditorParts: [] },
      pipelineTweaks: {
        ...state.pipelineTweaks,
        [pipelineId]: restTweak,
      },
      autoRunTrigger: state.autoRunTrigger + 1,
    });
  },

  applySemanticPreset: (preset) => {
    const state = get();
    const pipelineId = state.controls.pipelineId;
    const tweak = semanticPresetTweak(preset);
    const controls = { ...state.controls, ...tweak };
    set({
      controls,
      pipelineTweaks: {
        ...state.pipelineTweaks,
        [pipelineId]: { ...state.pipelineTweaks[pipelineId], ...tweak },
      },
      autoRunTrigger: state.autoRunTrigger + 1,
    });
  },
});
