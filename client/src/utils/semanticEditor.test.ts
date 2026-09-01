import { describe, expect, it } from "vitest";
import { editBox, normalizeBox } from "./edit";
import { materializeSemanticEditorParts, remapAxis, scaleValue } from "./semanticEditor";
import type { SemanticDebugFrame, SemanticEditorPart } from "../types/pipeline";

const frames: SemanticDebugFrame[] = [
  {
    index: 0,
    width: 20,
    height: 16,
    sourceWidth: 10,
    sourceHeight: 8,
    semanticOffset: { x: 2, y: 3 },
    files: { rawRgb: "", baseAlpha: "", samRgb: "", finalRgba: "" },
  },
];

describe("semantic editor coordinate utilities", () => {
  it("scales values and maps offsets between frame spaces", () => {
    expect(scaleValue(4, 10, 20)).toBe(8);
    expect(remapAxis(7, 2, 10, 4, 20, 10, 20)).toBe(14);
  });

  it("normalizes boxes and supports legacy box shapes", () => {
    expect(normalizeBox([9, 8, 2, 1], 10, 10)).toEqual([2, 1, 9, 8]);
    expect(editBox({ frame: 0, partId: "hat", type: "bbox", box: [2, 3, 8, 9] })).toEqual([2, 3, 6, 6]);
    expect(editBox({ frame: 0, partId: "hat", type: "bbox", x0: 1, y0: 2, x1: 5, y1: 7 })).toEqual([1, 2, 4, 5]);
  });

  it("materializes editor edits into the current frame coordinate space", () => {
    const part: SemanticEditorPart = {
      id: "hat",
      label: "Hat",
      prompt: "hat",
      mobility: "static",
      persistence: "always",
      edits: [{ frame: 0, partId: "hat", type: "positive_point", x: 20, y: 12 }],
    };

    const [materialized] = materializeSemanticEditorParts([part], frames, "preview-1");

    expect(materialized.edits[0]).toMatchObject({ frame: 0, x: 19, y: 12 });
    expect(materialized.edits[0].space).toMatchObject({
      coordinateSpace: "semantic_input_pre_upscale",
      frameWidth: 20,
      frameHeight: 16,
      previewId: "preview-1",
    });
  });
});
