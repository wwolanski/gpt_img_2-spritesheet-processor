import type { SemanticEdit } from "../types/pipeline";

export function editBox(edit: SemanticEdit): [number, number, number, number] | null {
  if (Array.isArray(edit.box) && edit.box.length === 4) {
    return [edit.box[0], edit.box[1], edit.box[2] - edit.box[0], edit.box[3] - edit.box[1]];
  }
  if ([edit.x0, edit.y0, edit.x1, edit.y1].every((value) => typeof value === "number")) {
    return [edit.x0!, edit.y0!, edit.x1! - edit.x0!, edit.y1! - edit.y0!];
  }
  return null;
}

export function editKey(partId: string, editIndex: number): string {
  return `${partId}-${editIndex}`;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function normalizeBox(
  box: [number, number, number, number],
  width: number,
  height: number,
): [number, number, number, number] {
  const x0 = clamp(Math.min(box[0], box[2]), 0, Math.max(1, width - 1));
  const y0 = clamp(Math.min(box[1], box[3]), 0, Math.max(1, height - 1));
  const x1 = clamp(Math.max(box[0], box[2]), x0 + 1, width);
  const y1 = clamp(Math.max(box[1], box[3]), y0 + 1, height);
  return [Math.round(x0), Math.round(y0), Math.round(x1), Math.round(y1)];
}
