import type { ControlsState, DescribeResponse, PipelineStageSpec, StageGroup, StageStatus } from "../types/pipeline";

export function stageGroups(config: DescribeResponse | undefined, controls: ControlsState): StageGroup[] {
  const pipeline = config?.pipelines.find((p) => p.id === controls.pipelineId);
  return (pipeline?.stages ?? []).map((stage) => groupForStage(config, stage, controls));
}

function groupForStage(
  config: DescribeResponse | undefined,
  stage: PipelineStageSpec,
  controls: ControlsState,
): StageGroup {
  const stageId = stage.id;
  const definition = config?.stageRegistry.find((r) => r.id === stageId);
  const base = {
    id: stageId,
    label: definition?.label ?? stageLabel(stageId),
    description: definition?.description ?? "",
    included: controls.pipelineStages[stageId] ?? stage.included,
    configurable: definition?.configurable ?? false,
  };
  if (stageId === "key-detect") return { ...base, fields: [] };
  if (stageId.endsWith("-mask") || stageId === "chroma-mask" || stageId === "pixel-mask")
    return {
      ...base,
      fields: ["transparentThreshold", "opaqueThreshold", "edgeSoftness", "edgeBlurSigma", "alphaCutoff"],
    };
  if (stageId === "despill")
    return {
      ...base,
      fields: [
        "despillStrength",
        "despillAlphaMode",
        "despillAlphaStrength",
        "neutralizeEdges",
        "neutralizeStrength",
        "edgeDarken",
      ],
    };
  if (stageId === "outline") return { ...base, fields: ["outlineWidth", "outlineOpacity", "outlineBlur"] };
  if (stageId === "alpha-cleanup") return { ...base, fields: ["alphaCleanupMinArea", "alphaCleanupCloseSize"] };
  if (stageId === "frame-detect") return { ...base, fields: ["cropPadding", "minFrameArea"] };
  if (stageId === "semantic-input") return { ...base, fields: ["semanticInputMode"] };
  if (stageId === "semantic-propose") return { ...base, fields: ["semanticEditorParts"] };
  if (stageId === "semantic-grounding")
    return {
      ...base,
      fields: [
        "semanticGroundingMinConfidence",
        "semanticGroundingAlphaCutoff",
        "semanticGroundingDilationRadius",
        "semanticGroundingAllowFrameReassign",
        "semanticGroundingFrameMinScore",
        "semanticGroundingProjectionMode",
        "semanticGroundingExpandRatio",
        "semanticGroundingExpandMinPx",
        "semanticGroundingEmitBbox",
        "semanticGroundingEmitPositivePoint",
      ],
    };
  if (stageId === "part-segment-track") return { ...base, fields: ["semanticMaskModel"] };
  if (stageId === "part-stabilize")
    return {
      ...base,
      fields: [
        "partStabilizeEnabled",
        "partRepairEnabled",
        "partRepairSearchScale",
        "partPatchLockStrength",
        "partMedianStrength",
      ],
    };
  if (stageId === "geometry-stabilize") return { ...base, fields: [] };
  if (stageId === "sheet-build") return { ...base, fields: ["framePadding"] };
  if (stageId === "flow-deflicker")
    return {
      ...base,
      fields: [
        "flowDeflickerStrength",
        "flowDeflickerRadius",
        "flowColorTolerance",
        "flowAlphaTolerance",
        "flowConsistencyTolerance",
        "flowMaxDisplacement",
        "flowConfidenceFloor",
      ],
    };
  if (stageId === "temporal-deflicker")
    return {
      ...base,
      fields: [
        "temporalDeflickerStrength",
        "temporalStaticCoverage",
        "temporalColorTolerance",
        "temporalAlphaTolerance",
      ],
    };
  if (stageId === "edge-extrude") return { ...base, fields: ["sheetExtrudePixels"] };
  if (stageId === "upscale") return { ...base, fields: ["upscaleMode"] };
  if (stageId === "metrics") return { ...base, fields: [] };
  return { ...base, fields: [] };
}

function stageLabel(stageId: string): string {
  return stageId
    .split("-")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}

export function buildStageStatuses(
  config: DescribeResponse | undefined,
  controls: ControlsState,
  status: StageStatus,
): Record<string, StageStatus> {
  return Object.fromEntries(stageGroups(config, controls).map((g) => [g.id, status]));
}
