import type { ControlsState, DescribeResponse, OptionValue } from "../types/pipeline";
import { slugify } from "./format";
import { numericFields } from "../constants/controls";
import { cloneControls, applyDefaults, defaultStageMapForPipeline } from "./pipeline";

export { numericFields };

export function buildOptions(controls: ControlsState): Record<string, OptionValue> {
  return {
    profile: controls.profile,
    transparentThreshold: controls.transparentThreshold,
    opaqueThreshold: controls.opaqueThreshold,
    edgeSoftness: controls.edgeSoftness,
    edgeBlurSigma: controls.edgeBlurSigma,
    despillStrength: controls.despillStrength,
    despillAlphaMode: controls.despillAlphaMode,
    despillAlphaStrength: controls.despillAlphaStrength,
    neutralizeEdges: controls.neutralizeEdges,
    neutralizeStrength: controls.neutralizeStrength,
    edgeDarken: controls.edgeDarken,
    outlineWidth: controls.outlineWidth,
    outlineOpacity: controls.outlineOpacity,
    outlineBlur: controls.outlineBlur,
    alphaCleanupMinArea: controls.alphaCleanupMinArea,
    alphaCleanupCloseSize: controls.alphaCleanupCloseSize,
    cropPadding: controls.cropPadding,
    framePadding: controls.framePadding,
    minFrameArea: controls.minFrameArea,
    alphaCutoff: controls.alphaCutoff,
    flowDeflickerStrength: controls.flowDeflickerStrength,
    flowDeflickerRadius: controls.flowDeflickerRadius,
    flowColorTolerance: controls.flowColorTolerance,
    flowAlphaTolerance: controls.flowAlphaTolerance,
    flowConsistencyTolerance: controls.flowConsistencyTolerance,
    flowMaxDisplacement: controls.flowMaxDisplacement,
    flowConfidenceFloor: controls.flowConfidenceFloor,
    temporalDeflickerStrength: controls.temporalDeflickerStrength,
    temporalStaticCoverage: controls.temporalStaticCoverage,
    temporalColorTolerance: controls.temporalColorTolerance,
    temporalAlphaTolerance: controls.temporalAlphaTolerance,
    sheetExtrudePixels: controls.sheetExtrudePixels,
    upscaleMode: controls.upscaleMode,
    pipelineStages: controls.pipelineStages,
    semanticInputMode: controls.semanticInputMode,
    semanticGroundingMinConfidence: controls.semanticGroundingMinConfidence,
    semanticGroundingAlphaCutoff: controls.semanticGroundingAlphaCutoff,
    semanticGroundingDilationRadius: controls.semanticGroundingDilationRadius,
    semanticGroundingAllowFrameReassign: controls.semanticGroundingAllowFrameReassign,
    semanticGroundingFrameMinScore: controls.semanticGroundingFrameMinScore,
    semanticGroundingProjectionMode: controls.semanticGroundingProjectionMode,
    semanticGroundingExpandRatio: controls.semanticGroundingExpandRatio,
    semanticGroundingExpandMinPx: controls.semanticGroundingExpandMinPx,
    semanticGroundingEmitBbox: controls.semanticGroundingEmitBbox,
    semanticGroundingEmitPositivePoint: controls.semanticGroundingEmitPositivePoint,
    semanticMaskModel: controls.semanticMaskModel,
    partStabilizeEnabled: controls.partStabilizeEnabled,
    partRepairEnabled: controls.partRepairEnabled,
    partRepairSearchScale: controls.partRepairSearchScale,
    partPatchLockStrength: controls.partPatchLockStrength,
    partMedianStrength: controls.partMedianStrength,
    semanticManualParts: controls.semanticManualParts,
    semanticEdits: controls.semanticEdits,
    semanticEditorParts: controls.semanticEditorParts,
  };
}

export function buildPipelineOptions(
  config: DescribeResponse | undefined,
  controls: ControlsState,
  pipelineIds: string[],
  pipelineTweaks: Record<string, Partial<ControlsState>>,
  profileOverride?: string,
): Record<string, Record<string, OptionValue>> {
  return Object.fromEntries(
    pipelineIds.map((pipelineId) => [
      pipelineId,
      buildOptions(controlsForPipeline(config, controls, pipelineId, controls.source, pipelineTweaks, profileOverride)),
    ]),
  );
}

export function variantKey(source: string, pipelineId: string): string {
  return `${source}::${pipelineId}`;
}

export function pipelineLabel(config: DescribeResponse | undefined, pipelineId: string): string {
  return config?.pipelines.find((p) => p.id === pipelineId)?.label ?? pipelineId;
}

export function controlsForPipeline(
  config: DescribeResponse | undefined,
  controls: ControlsState,
  pipelineId: string,
  source = controls.source,
  pipelineTweaks: Record<string, Partial<ControlsState>>,
  profileOverride?: string,
): ControlsState {
  const profile = profileOverride ?? controls.profile;
  const c = cloneControls(controls);
  if (config) {
    applyDefaults(c, config.defaults);
    const preset = config.profilePresets[profile];
    if (preset) applyDefaults(c, preset);
  }
  c.source = source;
  c.profile = profile;
  c.exportSlug = slugify(source || controls.exportSlug);
  c.pipelineId = pipelineId;
  c.pipelineStages = defaultStageMapForPipeline(config, pipelineId);
  const tweaks = pipelineTweaks[pipelineId] ?? {};
  return cloneControls({ ...c, ...tweaks });
}
