import React, { useRef, useEffect } from "react";
import { usePipelineStore } from "../stores/pipelineStore";
import { flowBlendRatio } from "../services/stabilization";
import type { SemanticPart } from "../types/pipeline";
import { decodeRleMask, colorToRgb } from "../utils/canvas";

type DrawState = {
  frameIndex: number;
  dx: number;
  dy: number;
  dw: number;
  dh: number;
  sourceWidth: number;
  sourceHeight: number;
  semanticFrameWidth: number;
  semanticFrameHeight: number;
  semanticSourceWidth: number;
  semanticSourceHeight: number;
  semanticOffsetX: number;
  semanticOffsetY: number;
  previewId: string;
  flipped: boolean;
};

function paintAnimBg(ctx: CanvasRenderingContext2D, w: number, h: number, bg: string) {
  if (bg === "checker") {
    for (let y = 0; y < h; y += 24) {
      for (let x = 0; x < w; x += 24) {
        ctx.fillStyle = (x / 24 + y / 24) % 2 === 0 ? "#c5cad3" : "#8892a0";
        ctx.fillRect(x, y, 24, 24);
      }
    }
  } else if (bg === "white") {
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, w, h);
  } else if (bg === "gray") {
    ctx.fillStyle = "#6b7a8a";
    ctx.fillRect(0, 0, w, h);
  } else if (bg === "black") {
    ctx.fillStyle = "#000000";
    ctx.fillRect(0, 0, w, h);
  }
}

function maskCanvasForPart(
  part: SemanticPart,
  frameIndex: number,
  width: number,
  height: number,
  cache: Map<string, HTMLCanvasElement>,
): HTMLCanvasElement | null {
  const encoded = part.masks?.[frameIndex];
  if (!encoded) return null;
  const key = `${part.id}:${frameIndex}:${width}:${height}:${encoded}`;
  const cached = cache.get(key);
  if (cached) return cached;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  const image = ctx.createImageData(width, height);
  const mask = decodeRleMask(encoded, width, height);
  const [r, g, b] = colorToRgb(part.color);
  for (let i = 0; i < mask.length; i++) {
    if (!mask[i]) continue;
    const j = i * 4;
    image.data[j] = r;
    image.data[j + 1] = g;
    image.data[j + 2] = b;
    image.data[j + 3] = 96;
  }
  ctx.putImageData(image, 0, 0);
  cache.set(key, canvas);
  return canvas;
}

export function AnimationCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animHandleRef = useRef(0);
  const startTimeRef = useRef(performance.now());
  const maskCacheRef = useRef(new Map<string, HTMLCanvasElement>());
  const lastDrawRef = useRef<DrawState | null>(null);

  const current = usePipelineStore((s) => s.current);
  const sheetImage = usePipelineStore((s) => s.sheetImage);
  const animBg = usePipelineStore((s) => s.animBg);
  const animPlaying = usePipelineStore((s) => s.animPlaying);
  const enabledFrames = usePipelineStore((s) => s.enabledFrames);
  const showParts = usePipelineStore((s) => s.showParts);
  const activePartId = usePipelineStore((s) => s.activePartId);
  const controls = usePipelineStore((s) => s.controls);
  const addSemanticEdit = usePipelineStore((s) => s.addSemanticEdit);
  const gamepadActive = usePipelineStore((s) => s.gamepadActive);
  const animFps = usePipelineStore((s) => s.animFps);
  const moveSpeed = usePipelineStore((s) => s.moveSpeed);

  const isPlayingRef = useRef(animPlaying);
  const wasPausedRef = useRef(!animPlaying);
  const pauseOffsetRef = useRef(0);
  const gamepadActiveRef = useRef(gamepadActive);
  const keysRef = useRef({ a: false, d: false });
  const offsetXRef = useRef(0);
  const flipXRef = useRef(false);
  const fpsRef = useRef(animFps);
  const moveSpeedRef = useRef(moveSpeed);

  useEffect(() => {
    isPlayingRef.current = animPlaying;
  }, [animPlaying]);

  useEffect(() => {
    fpsRef.current = animFps;
  }, [animFps]);

  useEffect(() => {
    moveSpeedRef.current = moveSpeed;
  }, [moveSpeed]);

  useEffect(() => {
    gamepadActiveRef.current = gamepadActive;
  }, [gamepadActive]);

  useEffect(() => {
    if (gamepadActive) {
      offsetXRef.current = 0;
      flipXRef.current = false;
    } else {
      keysRef.current = { a: false, d: false };
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (!gamepadActiveRef.current) return;
      const target = e.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      const k = e.key.toLowerCase();
      if (k === "a" || k === "d") {
        e.preventDefault();
        keysRef.current[k] = true;
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      const k = e.key.toLowerCase();
      if (k === "a" || k === "d") {
        keysRef.current[k] = false;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [gamepadActive]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    cancelAnimationFrame(animHandleRef.current);

    const tick = (time: number) => {
      animHandleRef.current = requestAnimationFrame(tick);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      paintAnimBg(ctx, canvas.width, canvas.height, animBg);

      const sheet = sheetImage;
      if (!sheet || !current || current.frames.length === 0) return;

      const frames = current.frames.filter((f) => enabledFrames.has(f.index));
      const activeFrames = frames.length > 0 ? frames : current.frames;

      if (isPlayingRef.current) {
        if (wasPausedRef.current) {
          startTimeRef.current = time - pauseOffsetRef.current;
          wasPausedRef.current = false;
        }
        pauseOffsetRef.current = time - startTimeRef.current;
      } else {
        if (!wasPausedRef.current) {
          pauseOffsetRef.current = time - startTimeRef.current;
          wasPausedRef.current = true;
        }
      }

      const frameIndex = Math.floor((pauseOffsetRef.current / 1000) * fpsRef.current) % activeFrames.length;
      const frame = activeFrames[frameIndex];
      if (!frame?.sheetBox) return;
      const box = frame.sheetBox;
      const debugFrame = current.semanticDebug?.frames.find((item) => item.index === frame.index);
      if (box.width <= 0 || box.height <= 0) return;
      const scale = Math.min((canvas.width * 0.56) / box.width, (canvas.height * 0.72) / box.height);
      const dw = box.width * scale;
      const dh = box.height * scale;
      const baseX = canvas.width * 0.12;
      const dy = canvas.height * 0.12;

      if (gamepadActiveRef.current) {
        if (keysRef.current.a) {
          offsetXRef.current -= moveSpeedRef.current;
          flipXRef.current = true;
        }
        if (keysRef.current.d) {
          offsetXRef.current += moveSpeedRef.current;
          flipXRef.current = false;
        }
        const minOffset = -baseX;
        const maxOffset = canvas.width - baseX - dw;
        offsetXRef.current = Math.max(minOffset, Math.min(maxOffset, offsetXRef.current));
      }

      const dx = baseX + offsetXRef.current;
      lastDrawRef.current = {
        frameIndex: frame.index,
        dx,
        dy,
        dw,
        dh,
        sourceWidth: frame.sourceBox.width,
        sourceHeight: frame.sourceBox.height,
        semanticFrameWidth: debugFrame?.width ?? frame.sourceBox.width,
        semanticFrameHeight: debugFrame?.height ?? frame.sourceBox.height,
        semanticSourceWidth: debugFrame?.sourceWidth ?? frame.sourceBox.width,
        semanticSourceHeight: debugFrame?.sourceHeight ?? frame.sourceBox.height,
        semanticOffsetX: debugFrame?.semanticOffset?.x ?? 0,
        semanticOffsetY: debugFrame?.semanticOffset?.y ?? 0,
        previewId: current.previewId,
        flipped: flipXRef.current,
      };

      ctx.save();
      if (flipXRef.current) {
        ctx.translate(dx + dw, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(sheet, box.x, box.y, box.width, box.height, 0, dy, dw, dh);
      } else {
        ctx.drawImage(sheet, box.x, box.y, box.width, box.height, dx, dy, dw, dh);
      }
      ctx.restore();

      if (showParts && current.semantic?.parts?.length) {
        const sourceBox = frame.sourceBox;
        for (const part of current.semantic.parts) {
          if (activePartId && part.id !== activePartId) continue;
          const maskCanvas = maskCanvasForPart(
            part,
            frame.index,
            sourceBox.width,
            sourceBox.height,
            maskCacheRef.current,
          );
          if (maskCanvas) {
            ctx.drawImage(maskCanvas, 0, 0, sourceBox.width, sourceBox.height, dx, dy, dw, dh);
          }
          const partBox = part.boxes?.[frame.index];
          if (!partBox || sourceBox.width <= 0 || sourceBox.height <= 0) continue;
          const px = dx + (partBox.x / sourceBox.width) * dw;
          const py = dy + (partBox.y / sourceBox.height) * dh;
          const pw = (partBox.width / sourceBox.width) * dw;
          const ph = (partBox.height / sourceBox.height) * dh;
          ctx.save();
          ctx.strokeStyle = part.color;
          ctx.lineWidth = activePartId === part.id ? 3 : 2;
          ctx.setLineDash(activePartId === part.id ? [] : [6, 4]);
          ctx.strokeRect(px, py, pw, ph);
          ctx.fillStyle = part.color;
          ctx.globalAlpha = 0.88;
          ctx.fillRect(px, Math.max(0, py - 18), Math.min(96, Math.max(34, part.label.length * 7 + 10)), 16);
          ctx.globalAlpha = 1;
          ctx.fillStyle = "#071019";
          ctx.font = "700 10px 'Avenir Next', 'Segoe UI', sans-serif";
          ctx.fillText(part.label, px + 5, Math.max(12, py - 6));
          ctx.restore();
        }
      }

      ctx.fillStyle = "rgba(10, 18, 28, 0.8)";
      ctx.fillRect(canvas.width * 0.72, canvas.height * 0.1, canvas.width * 0.2, canvas.height * 0.58);
      ctx.fillStyle = "#f4fbff";
      ctx.font = "600 14px 'Avenir Next', 'Segoe UI', sans-serif";
      ctx.fillText(`frame #${frame.index}`, canvas.width * 0.75, canvas.height * 0.18);
      ctx.font = "12px 'Avenir Next', 'Segoe UI', sans-serif";
      ctx.fillText(`pipeline ${current.pipelineId}`, canvas.width * 0.75, canvas.height * 0.26);
      ctx.fillText(`score ${current.metrics.score}`, canvas.width * 0.75, canvas.height * 0.34);
      ctx.fillText(`spill ${current.metrics.green_spill_ratio}`, canvas.width * 0.75, canvas.height * 0.42);
      ctx.fillText(`box ${box.width}x${box.height}`, canvas.width * 0.75, canvas.height * 0.5);

      const flowRatio = flowBlendRatio(current);
      if (flowRatio !== null) {
        ctx.fillText(`flow ${flowRatio}`, canvas.width * 0.75, canvas.height * 0.58);
      }
    };

    startTimeRef.current = performance.now();
    wasPausedRef.current = !animPlaying;
    pauseOffsetRef.current = 0;
    animHandleRef.current = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(animHandleRef.current);
  }, [current, sheetImage, animBg, enabledFrames, showParts, activePartId]);

  const handleClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!activePartId || !current) return;
    const draw = lastDrawRef.current;
    if (!draw || draw.sourceWidth <= 0 || draw.sourceHeight <= 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const sx = event.currentTarget.width / rect.width;
    const sy = event.currentTarget.height / rect.height;
    const px = (event.clientX - rect.left) * sx;
    const py = (event.clientY - rect.top) * sy;
    if (px < draw.dx || py < draw.dy || px > draw.dx + draw.dw || py > draw.dy + draw.dh) return;
    const localX = ((px - draw.dx) / draw.dw) * draw.sourceWidth;
    const localY = ((py - draw.dy) / draw.dh) * draw.sourceHeight;
    const scaleX = draw.sourceWidth / Math.max(1, draw.semanticSourceWidth);
    const scaleY = draw.sourceHeight / Math.max(1, draw.semanticSourceHeight);
    const semanticLocalX = (draw.flipped ? draw.sourceWidth - localX : localX) / Math.max(0.0001, scaleX);
    const semanticLocalY = localY / Math.max(0.0001, scaleY);
    const semanticX = Math.max(0, Math.min(draw.semanticFrameWidth - 1, draw.semanticOffsetX + semanticLocalX));
    const semanticY = Math.max(0, Math.min(draw.semanticFrameHeight - 1, draw.semanticOffsetY + semanticLocalY));
    addSemanticEdit({
      frame: draw.frameIndex,
      partId: activePartId,
      type: controls.semanticEditTool,
      x: Math.round(semanticX),
      y: Math.round(semanticY),
      space: {
        coordinateSpace: "semantic_input_pre_upscale",
        frameWidth: draw.semanticFrameWidth,
        frameHeight: draw.semanticFrameHeight,
        sourceWidth: draw.semanticSourceWidth,
        sourceHeight: draw.semanticSourceHeight,
        previewId: draw.previewId,
        frameCount: current.frames.length,
        frameInterpolationFactor: current.semanticDebug?.frameInterpolation?.factor ?? 1,
      },
    });
  };

  return React.createElement("canvas", {
    ref: canvasRef,
    id: "animation-canvas",
    width: 920,
    height: 360,
    onClick: handleClick,
  });
}
