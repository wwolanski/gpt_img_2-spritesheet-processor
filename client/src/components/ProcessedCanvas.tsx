import React, { useRef, useEffect } from "react";
import { usePipelineStore } from "../stores/pipelineStore";
import { paintChecker } from "../utils/canvas";

export function ProcessedCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const current = usePipelineStore((s) => s.current);
  const processedImage = usePipelineStore((s) => s.processedImage);
  const showBoxes = usePipelineStore((s) => s.showBoxes);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    paintChecker(ctx, canvas.width, canvas.height, 18);

    const img = processedImage;
    if (!img || !current) return;

    const scale = Math.min(canvas.width / img.width, canvas.height / img.height);
    const dw = img.width * scale;
    const dh = img.height * scale;
    const ox = (canvas.width - dw) / 2;
    const oy = (canvas.height - dh) / 2;
    ctx.drawImage(img, ox, oy, dw, dh);

    if (showBoxes) {
      ctx.save();
      ctx.strokeStyle = "#6fffc9";
      ctx.lineWidth = 2;
      ctx.setLineDash([8, 6]);
      ctx.font = "12px 'Avenir Next', 'Segoe UI', sans-serif";
      ctx.fillStyle = "#f4fbff";
      for (const frame of current.frames) {
        const x = ox + frame.sourceBox.x * scale;
        const y = oy + frame.sourceBox.y * scale;
        ctx.strokeRect(x, y, frame.sourceBox.width * scale, frame.sourceBox.height * scale);
        ctx.fillText(`#${frame.index}`, x + 8, y + 16);
      }
      ctx.restore();
    }
  }, [current, processedImage, showBoxes]);

  return React.createElement(
    "div",
    { className: "source-card" },
    React.createElement("h3", null, "Processed + boxes"),
    React.createElement("canvas", {
      ref: canvasRef,
      id: "processed-canvas",
      width: 960,
      height: 420,
    }),
  );
}
