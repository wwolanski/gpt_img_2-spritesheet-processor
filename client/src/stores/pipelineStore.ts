import { create } from "zustand";
import type { ControlsState, VariantPreview } from "../types/pipeline";
import type { PipelineState } from "./pipelineStoreTypes";

import { variantKey, pipelineLabel } from "../utils/controls";
import {
  cloneControls,
  applyDefaults,
  syncProfileFromSource,
  syncPipelineFromProfile,
  applyTweaksForPipeline,
} from "../utils/pipeline";
import { buildStageStatuses, stageGroups } from "../utils/stage";
import { slugify } from "../utils/format";
import { defaultControls, isNumericControlField } from "../constants/controls";
import {
  clearSemanticCoordinateEdits,
  clearSemanticCoordinateTweaks,
  cloneSemanticEditorPart,
  materializeSemanticEditorParts,
  semanticResetFields,
} from "../utils/semanticEditor";
import { createSemanticActions } from "./semanticSlice";

export const usePipelineStore = create<PipelineState>((set, get) => ({
  config: undefined,
  sources: [],
  controls: { ...defaultControls, pipelineStages: {} },
  pipelineTweaks: {},
  variants: [],
  activeVariantId: null,
  current: undefined,
  activeStageId: null,
  stageStatuses: {},
  status: "",
  exportStatus: "",
  loading: false,
  showBoxes: true,
  showParts: true,
  activePartId: null,
  activeEditId: null,
  animBg: "checker",
  autoRunTrigger: 0,
  autoRunEnabled: true,
  animPlaying: true,
  enabledFrames: new Set<number>(),
  gamepadActive: false,
  animFps: 7,
  moveSpeed: 5,
  processedImage: undefined,
  sheetImage: undefined,

  /* ─── Init ─── */
  initConfig: (config, firstSource) => {
    const controls = { ...defaultControls };
    applyDefaults(controls, config.defaults);
    controls.source = firstSource;
    controls.exportSlug = slugify(firstSource);

    const synced = syncProfileFromSource(controls, config, {});
    const groups = stageGroups(config, synced);
    set({
      config,
      sources: [],
      controls: synced,
      status: `Gotowe. Input dir: ${config.paths.sources}`,
      activeStageId: groups.find((g) => g.fields.length > 0)?.id ?? null,
      stageStatuses: buildStageStatuses(config, synced, "idle"),
    });
  },

  setSources: (sources) => set({ sources }),

  /* ─── Controls ─── */
  setControl: <Key extends keyof ControlsState>(field: Key, value: ControlsState[Key]) => {
    const state = get();
    const resetSemanticEdits = semanticResetFields.has(field);
    const basePipelineTweaks = resetSemanticEdits
      ? clearSemanticCoordinateTweaks(state.pipelineTweaks)
      : state.pipelineTweaks;
    let controls = { ...state.controls, [field]: value };
    if (resetSemanticEdits) {
      controls = clearSemanticCoordinateEdits(controls);
    }

    if (field === "source") {
      controls.exportSlug = slugify(String(value));
      controls.profile = "auto";
      const synced = syncProfileFromSource(controls, state.config, basePipelineTweaks);
      set({
        controls: synced,
        pipelineTweaks: basePipelineTweaks,
        variants: [],
        current: undefined,
        activeVariantId: null,
        autoRunTrigger: state.autoRunTrigger + 1,
      });
      return;
    }

    if (field === "profile") {
      const synced = syncPipelineFromProfile(controls, state.config, basePipelineTweaks);
      set({ controls: synced, pipelineTweaks: basePipelineTweaks, autoRunTrigger: state.autoRunTrigger + 1 });
      return;
    }

    if (field === "pipelineId") {
      const synced = applyTweaksForPipeline(controls, state.config, String(value), basePipelineTweaks);
      set({ controls: synced, pipelineTweaks: basePipelineTweaks, autoRunTrigger: state.autoRunTrigger + 1 });
      return;
    }

    if (field === "exportSlug") {
      set({ controls });
      return;
    }

    if (isNumericControlField(field) || field === "pipelineStages") {
      const pipelineId = controls.pipelineId;
      const tweak = { ...basePipelineTweaks[pipelineId], [field]: value };
      const pipelineTweaks = { ...basePipelineTweaks, [pipelineId]: tweak };
      const synced = applyTweaksForPipeline(controls, state.config, pipelineId, pipelineTweaks);
      set({ controls: synced, pipelineTweaks, autoRunTrigger: state.autoRunTrigger + 1 });
    } else {
      const pipelineId = controls.pipelineId;
      const tweak = { ...basePipelineTweaks[pipelineId], [field]: value };
      set({
        controls,
        pipelineTweaks: { ...basePipelineTweaks, [pipelineId]: tweak },
        autoRunTrigger: state.autoRunTrigger + 1,
      });
    }
  },

  saveTweak: (field) => {
    const { controls, pipelineTweaks, config } = get();
    const pipelineId = controls.pipelineId;
    const synced = applyTweaksForPipeline(controls, config, pipelineId, {
      ...pipelineTweaks,
      [pipelineId]: { ...pipelineTweaks[pipelineId], [field]: controls[field] },
    });
    set({
      controls: synced,
      pipelineTweaks: {
        ...pipelineTweaks,
        [pipelineId]: { ...pipelineTweaks[pipelineId], [field]: controls[field] },
      },
    });
  },

  /* ─── UI state ─── */
  setActiveStageId: (id) => set({ activeStageId: id }),
  setShowBoxes: (v) => set({ showBoxes: v }),
  setShowParts: (v) => set({ showParts: v }),
  setActivePartId: (id) => set({ activePartId: id }),
  setActiveEditId: (id) => set({ activeEditId: id }),
  setAnimBg: (v) => set({ animBg: v }),
  setAnimPlaying: (v) => set({ animPlaying: v }),
  toggleFrame: (frameIndex) => {
    const state = get();
    const next = new Set(state.enabledFrames);
    if (next.has(frameIndex)) {
      next.delete(frameIndex);
    } else {
      next.add(frameIndex);
    }
    set({ enabledFrames: next });
  },
  resetEnabledFrames: (indexes) => set({ enabledFrames: new Set(indexes) }),
  setGamepadActive: (v) => set({ gamepadActive: v }),
  setAnimFps: (v) => set({ animFps: v }),
  setMoveSpeed: (v) => set({ moveSpeed: v }),
  setStatus: (v) => set({ status: v }),
  setExportStatus: (v) => set({ exportStatus: v }),
  setLoading: (v) => set({ loading: v }),

  setCurrent: (result, label, ctrlOverride) => {
    const state = get();
    let controls = ctrlOverride ?? {
      ...state.controls,
      source: result.source,
      pipelineId: result.pipelineId,
      pipelineStages: result.pipelineStages,
    };
    if (!ctrlOverride && controls.semanticEditorParts.length > 0 && result.semanticDebug?.frames?.length) {
      const remappedParts = materializeSemanticEditorParts(
        controls.semanticEditorParts,
        result.semanticDebug.frames,
        result.previewId,
        result.semanticDebug.frameInterpolation,
      );
      controls = { ...controls, semanticEditorParts: remappedParts };
    }
    const activeId = variantKey(result.source, result.pipelineId);
    const existingIndex = state.variants.findIndex((v) => v.id === activeId);
    const ready: VariantPreview = {
      id: activeId,
      label,
      pipelineId: result.pipelineId,
      source: result.source,
      controls: cloneControls(controls),
      result,
      status: "ready",
    };
    const variants = [...state.variants];
    if (existingIndex >= 0) {
      variants[existingIndex] = ready;
    } else if (!variants.some((v) => v.result?.previewId === result.previewId)) {
      variants.unshift(ready);
    }

    const newIndexes = result.frames.map((f) => f.index);
    const currentIndexes = state.current?.frames.map((f) => f.index) ?? [];
    const sameFrames =
      newIndexes.length === currentIndexes.length && newIndexes.every((idx, i) => idx === currentIndexes[i]);
    const enabledFrames = sameFrames ? state.enabledFrames : new Set(newIndexes);

    const nextPipelineTweaks =
      !ctrlOverride && controls.semanticEditorParts.length > 0
        ? {
            ...state.pipelineTweaks,
            [controls.pipelineId]: {
              ...state.pipelineTweaks[controls.pipelineId],
              semanticEditorParts: controls.semanticEditorParts.map(cloneSemanticEditorPart),
            },
          }
        : state.pipelineTweaks;

    set({
      current: result,
      controls: cloneControls(controls),
      pipelineTweaks: nextPipelineTweaks,
      activeVariantId: activeId,
      variants,
      enabledFrames,
      stageStatuses: buildStageStatuses(state.config, controls, "ready"),
    });
  },

  ...createSemanticActions(set, get),

  setVariants: (variants) => set({ variants }),

  upsertRunningVariant: (pipelineId, source, ctrl) => {
    const state = get();
    const id = variantKey(source, pipelineId);
    const idx = state.variants.findIndex((v) => v.id === id);
    const running: VariantPreview = {
      id,
      label: pipelineLabel(state.config, pipelineId),
      pipelineId,
      source,
      controls: cloneControls(ctrl),
      status: "running",
      result: idx >= 0 ? state.variants[idx].result : undefined,
    };
    const variants = [...state.variants];
    if (idx >= 0) {
      variants[idx] = running;
    } else {
      variants.unshift(running);
    }
    set({ variants, stageStatuses: buildStageStatuses(state.config, ctrl, "running") });
  },

  markVariantError: (pipelineId, source, error) => {
    const state = get();
    const idx = state.variants.findIndex((v) => v.pipelineId === pipelineId && v.source === source);
    if (idx < 0) return;
    const variants = [...state.variants];
    variants[idx] = {
      ...variants[idx],
      status: "error",
      error: error instanceof Error ? error.message : String(error),
    };
    set({
      variants,
      stageStatuses: buildStageStatuses(state.config, state.controls, "error"),
    });
  },

  setStageStatuses: (status) => {
    const state = get();
    set({ stageStatuses: buildStageStatuses(state.config, state.controls, status) });
  },

  setPreviewImages: (processedImage, sheetImage) => set({ processedImage, sheetImage }),
  setAutoRunEnabled: (autoRunEnabled) => set({ autoRunEnabled }),
}));
