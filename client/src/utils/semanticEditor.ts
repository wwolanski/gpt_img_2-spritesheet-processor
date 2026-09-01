import type {
  ControlsState,
  SemanticDebugFrame,
  SemanticDebugMetadata,
  SemanticEdit,
  SemanticEditorPart,
  SemanticEditorPresetSettings,
} from "../types/pipeline";
import { clamp, normalizeBox } from "./edit";

export const semanticResetFields = new Set<keyof ControlsState>(["source"]);

export function clearSemanticCoordinateEdits(controls: ControlsState): ControlsState {
  return { ...controls, semanticEdits: [], semanticEditorParts: [] };
}

export function clearSemanticCoordinateTweaks(
  pipelineTweaks: Record<string, Partial<ControlsState>>,
): Record<string, Partial<ControlsState>> {
  return Object.fromEntries(
    Object.entries(pipelineTweaks).map(([pipelineId, tweaks]) => {
      const { semanticEdits: _semanticEdits, semanticEditorParts: _semanticEditorParts, ...rest } = tweaks;
      return [pipelineId, rest];
    }),
  );
}

const semanticPresetFields: Array<keyof SemanticEditorPresetSettings> = [
  "semanticInputMode",
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
  "semanticMaskModel",
  "semanticEditorParts",
];

export function cloneSemanticEdit(edit: SemanticEdit): SemanticEdit {
  return {
    ...edit,
    box: Array.isArray(edit.box) ? [...edit.box] : undefined,
    space: edit.space ? { ...edit.space } : undefined,
  };
}

export function cloneSemanticEditorPart(part: SemanticEditorPart): SemanticEditorPart {
  return {
    ...part,
    stabilizeSettings: part.stabilizeSettings ? { ...part.stabilizeSettings } : undefined,
    edits: part.edits.map(cloneSemanticEdit),
  };
}

export function editSpace(
  frame: {
    width: number;
    height: number;
    sourceWidth?: number;
    sourceHeight?: number;
    semanticOffset?: { x: number; y: number };
  },
  previewId: string,
  frameCount?: number,
  frameInterpolationFactor?: number,
) {
  return {
    coordinateSpace: "semantic_input_pre_upscale",
    frameWidth: frame.width,
    frameHeight: frame.height,
    sourceWidth: frame.sourceWidth,
    sourceHeight: frame.sourceHeight,
    offsetX: frame.semanticOffset?.x,
    offsetY: frame.semanticOffset?.y,
    previewId,
    frameCount,
    frameInterpolationFactor,
  };
}

export function scaleValue(value: number, sourceSize: number, targetSize: number): number {
  if (!Number.isFinite(value) || sourceSize <= 0 || targetSize <= 0 || sourceSize === targetSize) {
    return value;
  }
  return (value / sourceSize) * targetSize;
}

export function remapAxis(
  value: number,
  sourceOffset: number | undefined,
  sourceSize: number | undefined,
  targetOffset: number | undefined,
  targetSize: number | undefined,
  fallbackSourceSize: number,
  fallbackTargetSize: number,
): number {
  if (fallbackSourceSize === fallbackTargetSize) return value;
  if (
    sourceOffset !== undefined &&
    sourceSize !== undefined &&
    targetOffset !== undefined &&
    targetSize !== undefined &&
    sourceSize > 0 &&
    targetSize > 0
  ) {
    return targetOffset + scaleValue(value - sourceOffset, sourceSize, targetSize);
  }
  return scaleValue(value, fallbackSourceSize, fallbackTargetSize);
}

export function editBoxRaw(edit: SemanticEdit): [number, number, number, number] | null {
  if (Array.isArray(edit.box) && edit.box.length === 4) {
    return [edit.box[0], edit.box[1], edit.box[2], edit.box[3]];
  }
  if ([edit.x0, edit.y0, edit.x1, edit.y1].every((value) => typeof value === "number")) {
    return [edit.x0!, edit.y0!, edit.x1!, edit.y1!];
  }
  return null;
}

export function materializeSemanticEditorParts(
  parts: SemanticEditorPart[],
  frames: SemanticDebugFrame[],
  previewId: string,
  interpolation?: SemanticDebugMetadata["frameInterpolation"],
): SemanticEditorPart[] {
  const frameByIndex = new Map(frames.map((item) => [item.index, item]));
  const factor = interpolation?.enabled ? interpolation.factor : 1;
  const sourceFrameCount = interpolation?.sourceFrameCount ?? frames.length;
  const outputFrameCount = interpolation?.outputFrameCount ?? frames.length;
  return parts.map((part) => ({
    ...part,
    edits: part.edits.reduce<SemanticEdit[]>((acc, edit) => {
      const authoredFrameCount = edit.space?.frameCount;
      const legacySourceTimebase =
        factor > 1 &&
        edit.frame < sourceFrameCount &&
        (authoredFrameCount === undefined || authoredFrameCount === sourceFrameCount);
      const targetFrameIndex = legacySourceTimebase ? edit.frame * factor : edit.frame;
      const targetFrame = frameByIndex.get(targetFrameIndex);
      if (!targetFrame) return acc;
      const sourceWidth = edit.space?.frameWidth ?? targetFrame.width;
      const sourceHeight = edit.space?.frameHeight ?? targetFrame.height;
      const sourceOffsetX = edit.space?.offsetX;
      const sourceOffsetY = edit.space?.offsetY;
      const targetOffsetX = targetFrame.semanticOffset?.x;
      const targetOffsetY = targetFrame.semanticOffset?.y;
      const sourcePartWidth = edit.space?.sourceWidth;
      const sourcePartHeight = edit.space?.sourceHeight;
      const targetPartWidth = targetFrame.sourceWidth;
      const targetPartHeight = targetFrame.sourceHeight;
      if (edit.type === "bbox") {
        const box = editBoxRaw(edit);
        if (!box) return acc;
        const [x0, y0, x1, y1] = normalizeBox(
          [
            remapAxis(
              box[0],
              sourceOffsetX,
              sourcePartWidth,
              targetOffsetX,
              targetPartWidth,
              sourceWidth,
              targetFrame.width,
            ),
            remapAxis(
              box[1],
              sourceOffsetY,
              sourcePartHeight,
              targetOffsetY,
              targetPartHeight,
              sourceHeight,
              targetFrame.height,
            ),
            remapAxis(
              box[2],
              sourceOffsetX,
              sourcePartWidth,
              targetOffsetX,
              targetPartWidth,
              sourceWidth,
              targetFrame.width,
            ),
            remapAxis(
              box[3],
              sourceOffsetY,
              sourcePartHeight,
              targetOffsetY,
              targetPartHeight,
              sourceHeight,
              targetFrame.height,
            ),
          ],
          targetFrame.width,
          targetFrame.height,
        );
        acc.push({
          frame: targetFrameIndex,
          partId: part.id,
          type: edit.type,
          box: [x0, y0, x1, y1],
          space: editSpace(targetFrame, previewId, outputFrameCount, factor),
        });
        return acc;
      }
      const x = clamp(
        remapAxis(
          edit.x ?? 0,
          sourceOffsetX,
          sourcePartWidth,
          targetOffsetX,
          targetPartWidth,
          sourceWidth,
          targetFrame.width,
        ),
        0,
        targetFrame.width - 1,
      );
      const y = clamp(
        remapAxis(
          edit.y ?? 0,
          sourceOffsetY,
          sourcePartHeight,
          targetOffsetY,
          targetPartHeight,
          sourceHeight,
          targetFrame.height,
        ),
        0,
        targetFrame.height - 1,
      );
      acc.push({
        frame: targetFrameIndex,
        partId: part.id,
        type: edit.type,
        x: Math.round(x),
        y: Math.round(y),
        space: editSpace(targetFrame, previewId, outputFrameCount, factor),
      });
      return acc;
    }, []),
  }));
}

export function semanticPresetTweak(
  preset: SemanticEditorPresetSettings,
): Pick<ControlsState, keyof SemanticEditorPresetSettings> {
  const tweak = {} as Pick<ControlsState, keyof SemanticEditorPresetSettings>;
  for (const field of semanticPresetFields) {
    (tweak as Record<string, unknown>)[field] =
      field === "semanticEditorParts" ? preset.semanticEditorParts.map(cloneSemanticEditorPart) : preset[field];
  }
  return tweak;
}

export function materializePresetSettings(
  preset: SemanticEditorPresetSettings,
  frames: SemanticDebugFrame[],
  previewId: string,
  interpolation?: SemanticDebugMetadata["frameInterpolation"],
): SemanticEditorPresetSettings {
  return {
    ...preset,
    semanticEditorParts: materializeSemanticEditorParts(preset.semanticEditorParts, frames, previewId, interpolation),
  };
}
