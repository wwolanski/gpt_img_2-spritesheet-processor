import { afterEach, describe, expect, it } from "vitest";
import { defaultControls } from "../constants/controls";
import type { DescribeResponse } from "../types/pipeline";
import { usePipelineStore } from "./pipelineStore";

const initialState = usePipelineStore.getState();

const config: DescribeResponse = {
  defaults: {},
  profiles: ["auto", "outline", "pixelart"],
  profilePresets: { outline: {}, pixelart: {} },
  stageRegistry: [
    { id: "chroma-mask", label: "Chroma", description: "", configurable: true },
    { id: "metrics", label: "Metrics", description: "", configurable: false },
  ],
  pipelines: [
    {
      id: "greenscreen-clean",
      enabled: true,
      label: "Green",
      description: "",
      profile_hint: "outline",
      stages: [
        { id: "chroma-mask", included: true },
        { id: "metrics", included: true },
      ],
      optionOverrides: {},
    },
    {
      id: "pixel-solid",
      enabled: true,
      label: "Pixel",
      description: "",
      profile_hint: "pixelart",
      stages: [
        { id: "chroma-mask", included: true },
        { id: "metrics", included: true },
      ],
      optionOverrides: {},
    },
  ],
  capabilities: { rembg: false, auraSr: false, sam3: false, rife: false, workers: 1 },
  paths: { sources: "sources", publicAssets: "public/assets" },
};

afterEach(() => {
  usePipelineStore.setState(initialState, true);
});

describe("pipeline store", () => {
  it("initializes profile and pipeline from the selected source", () => {
    usePipelineStore.getState().initConfig(config, "pirate_pixelart.png");

    const state = usePipelineStore.getState();
    expect(state.controls.profile).toBe("pixelart");
    expect(state.controls.pipelineId).toBe("pixel-solid");
    expect(state.controls.exportSlug).toBe("pirate_pixelart");
    expect(state.stageStatuses).toEqual({ "chroma-mask": "idle", metrics: "idle" });
  });

  it("keeps numeric control changes as per-pipeline tweaks", () => {
    usePipelineStore.getState().initConfig(config, "pirate_outline.png");
    const before = usePipelineStore.getState().autoRunTrigger;

    usePipelineStore.getState().setControl("outlineWidth", 3);

    const state = usePipelineStore.getState();
    expect(state.controls.outlineWidth).toBe(3);
    expect(state.pipelineTweaks[state.controls.pipelineId]?.outlineWidth).toBe(3);
    expect(state.autoRunTrigger).toBe(before + 1);
  });

  it("stores semantic edits in both controls and the active pipeline tweak", () => {
    usePipelineStore.getState().initConfig(config, "pirate_outline.png");
    usePipelineStore.getState().addSemanticEdit({
      frame: 0,
      partId: "hat",
      type: "positive_point",
      x: 4,
      y: 5,
    });

    const state = usePipelineStore.getState();
    expect(state.controls.semanticEdits).toHaveLength(1);
    expect(state.pipelineTweaks[state.controls.pipelineId]?.semanticEdits).toEqual(state.controls.semanticEdits);
  });

  it("does not mutate the default controls object", () => {
    expect(defaultControls.semanticEdits).toEqual([]);
    usePipelineStore.getState().setControl("source", "pirate_outline.png");
    expect(defaultControls.source).toBe("");
  });
});
