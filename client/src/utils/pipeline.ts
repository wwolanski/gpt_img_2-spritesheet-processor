import type { ControlsState, DescribeResponse } from "../types/pipeline";

export function applyDefaults(
  target: ControlsState,
  defaults: Partial<Record<string, number | string | boolean>>,
): void {
  for (const [key, value] of Object.entries(defaults)) {
    if (!(key in target) || value === undefined) continue;
    (target as unknown as Record<string, number | string | boolean>)[key] = value;
  }
}

export function cloneControls(controls: ControlsState): ControlsState {
  return { ...controls, pipelineStages: { ...controls.pipelineStages } };
}

export function defaultStageMapForPipeline(
  config: DescribeResponse | undefined,
  pipelineId: string,
): Record<string, boolean> {
  const pipeline = config?.pipelines.find((p) => p.id === pipelineId);
  return Object.fromEntries((pipeline?.stages ?? []).map((stage) => [stage.id, stage.included]));
}

export function applyTweaksForPipeline(
  controls: ControlsState,
  config: DescribeResponse | undefined,
  pipelineId: string,
  pipelineTweaks: Record<string, Partial<ControlsState>>,
): ControlsState {
  const tweaks = pipelineTweaks[pipelineId];
  const baseStages = defaultStageMapForPipeline(config, pipelineId);
  return tweaks
    ? { ...controls, pipelineStages: baseStages, ...tweaks, pipelineId }
    : { ...controls, pipelineStages: baseStages, pipelineId };
}

export function syncProfileFromSource(
  controls: ControlsState,
  config: DescribeResponse | undefined,
  pipelineTweaks: Record<string, Partial<ControlsState>>,
): ControlsState {
  const lowered = controls.source.toLowerCase();
  let profile = "outline";
  if (lowered.includes("pixel")) profile = "pixelart";
  else if (lowered.includes("superthick") || lowered.includes("thick")) profile = "thick-outline";
  return syncPipelineFromProfile({ ...controls, profile }, config, pipelineTweaks);
}

export function syncPipelineFromProfile(
  controls: ControlsState,
  config: DescribeResponse | undefined,
  pipelineTweaks: Record<string, Partial<ControlsState>>,
): ControlsState {
  if (controls.profile === "pixelart") {
    return applyTweaksForPipeline(
      { ...controls, pipelineId: "pixel-solid", outlineWidth: 0, edgeBlurSigma: 0 },
      config,
      "pixel-solid",
      pipelineTweaks,
    );
  }
  if (controls.profile === "thick-outline") {
    return applyTweaksForPipeline(
      {
        ...controls,
        pipelineId: "outline-ink",
        outlineWidth: Math.max(2, controls.outlineWidth),
        edgeBlurSigma: Math.max(0.35, controls.edgeBlurSigma),
      },
      config,
      "outline-ink",
      pipelineTweaks,
    );
  }
  return applyTweaksForPipeline(
    {
      ...controls,
      pipelineId: "greenscreen-clean",
      outlineWidth: Math.min(controls.outlineWidth, 1),
      edgeBlurSigma: Math.max(0.35, controls.edgeBlurSigma),
    },
    config,
    "greenscreen-clean",
    pipelineTweaks,
  );
}
