import React, { useEffect, useRef } from "react";
import { usePipelineStore } from "../stores/pipelineStore";
import type { FrameMetadata, SemanticPart } from "../types/pipeline";
import { THUMB_SIZE } from "../constants/animation";
import { decodeRleMask, colorToRgb, paintChecker } from "../utils/canvas";

function FrameThumbnail({
  frame,
  enabled,
  sheetImage,
  showParts,
  parts,
}: {
  frame: FrameMetadata;
  enabled: boolean;
  sheetImage: HTMLImageElement | undefined;
  showParts: boolean;
  parts: SemanticPart[] | undefined;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const toggleFrame = usePipelineStore((s) => s.toggleFrame);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, THUMB_SIZE, THUMB_SIZE);
    paintChecker(ctx, THUMB_SIZE, THUMB_SIZE, 12);

    const sheet = sheetImage;
    const box = frame.sheetBox;
    if (!sheet || box.width <= 0 || box.height <= 0) return;

    const scale = Math.min((THUMB_SIZE - 8) / box.width, (THUMB_SIZE - 8) / box.height);
    const dw = box.width * scale;
    const dh = box.height * scale;
    const dx = (THUMB_SIZE - dw) / 2;
    const dy = (THUMB_SIZE - dh) / 2;

    ctx.drawImage(sheet, box.x, box.y, box.width, box.height, dx, dy, dw, dh);
    if (showParts && parts?.length) {
      const sourceBox = frame.sourceBox;
      for (const part of parts) {
        const encoded = part.masks?.[frame.index];
        if (encoded && sourceBox.width > 0 && sourceBox.height > 0) {
          const mask = decodeRleMask(encoded, sourceBox.width, sourceBox.height);
          const overlay = ctx.createImageData(sourceBox.width, sourceBox.height);
          const [r, g, b] = colorToRgb(part.color);
          for (let i = 0; i < mask.length; i++) {
            if (!mask[i]) continue;
            const j = i * 4;
            overlay.data[j] = r;
            overlay.data[j + 1] = g;
            overlay.data[j + 2] = b;
            overlay.data[j + 3] = 90;
          }
          const temp = document.createElement("canvas");
          temp.width = sourceBox.width;
          temp.height = sourceBox.height;
          temp.getContext("2d")?.putImageData(overlay, 0, 0);
          ctx.drawImage(temp, 0, 0, sourceBox.width, sourceBox.height, dx, dy, dw, dh);
        }
        const partBox = part.boxes?.[frame.index];
        if (!partBox || sourceBox.width <= 0 || sourceBox.height <= 0) continue;
        ctx.strokeStyle = part.color;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(
          dx + (partBox.x / sourceBox.width) * dw,
          dy + (partBox.y / sourceBox.height) * dh,
          (partBox.width / sourceBox.width) * dw,
          (partBox.height / sourceBox.height) * dh,
        );
      }
    }
  }, [frame, sheetImage, showParts, parts]);

  return React.createElement(
    "button",
    {
      type: "button",
      className: `frame-thumb ${enabled ? "frame-thumb-enabled" : "frame-thumb-disabled"}`,
      onClick: () => toggleFrame(frame.index),
      title: `Frame ${frame.index}`,
    },
    React.createElement("canvas", {
      ref: canvasRef,
      className: "frame-thumb-canvas",
      width: THUMB_SIZE,
      height: THUMB_SIZE,
    }),
    React.createElement("span", { className: "frame-thumb-index" }, String(frame.index)),
  );
}

export function FrameStrip() {
  const current = usePipelineStore((s) => s.current);
  const enabledFrames = usePipelineStore((s) => s.enabledFrames);
  const sheetImage = usePipelineStore((s) => s.sheetImage);
  const showParts = usePipelineStore((s) => s.showParts);

  if (!current || current.frames.length === 0) return null;

  return React.createElement(
    "div",
    { className: "frame-strip" },
    current.frames.map((frame) =>
      React.createElement(FrameThumbnail, {
        key: frame.index,
        frame,
        enabled: enabledFrames.has(frame.index),
        sheetImage,
        showParts,
        parts: current.semantic?.parts,
      }),
    ),
  );
}
