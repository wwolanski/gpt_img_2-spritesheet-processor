export function decodeRleMask(encoded: string | undefined, width: number, height: number): Uint8Array {
  const total = width * height;
  const out = new Uint8Array(total);
  if (!encoded) return out;
  const counts = encoded
    .split(",")
    .map((part) => Number(part))
    .filter((value) => Number.isFinite(value));
  let offset = 0;
  let value = 0;
  for (const count of counts) {
    if (value === 1) out.fill(1, offset, Math.min(total, offset + count));
    offset += Math.max(0, count);
    value = 1 - value;
    if (offset >= total) break;
  }
  return out;
}

export function colorToRgb(color: string): [number, number, number] {
  const hex = color.replace("#", "");
  return [
    Number.parseInt(hex.slice(0, 2), 16) || 255,
    Number.parseInt(hex.slice(2, 4), 16) || 255,
    Number.parseInt(hex.slice(4, 6), 16) || 255,
  ];
}

export function paintChecker(ctx: CanvasRenderingContext2D, w: number, h: number, tile: number) {
  for (let y = 0; y < h; y += tile) {
    for (let x = 0; x < w; x += tile) {
      ctx.fillStyle = (x / tile + y / tile) % 2 === 0 ? "#c5cad3" : "#8892a0";
      ctx.fillRect(x, y, tile, tile);
    }
  }
}

export function fitRect(width: number, height: number) {
  if (width <= 0 || height <= 0) return { left: 0, top: 0, width: 100, height: 100 };
  if (width >= height) {
    const fittedHeight = (height / width) * 100;
    return { left: 0, top: (100 - fittedHeight) / 2, width: 100, height: fittedHeight };
  }
  const fittedWidth = (width / height) * 100;
  return { left: (100 - fittedWidth) / 2, top: 0, width: fittedWidth, height: 100 };
}

export function overlayBoxStyle(frame: { width: number; height: number }, box: [number, number, number, number]) {
  const fit = fitRect(frame.width, frame.height);
  const [x, y, width, height] = box;
  return {
    left: `${fit.left + (x / frame.width) * fit.width}%`,
    top: `${fit.top + (y / frame.height) * fit.height}%`,
    width: `${(width / frame.width) * fit.width}%`,
    height: `${(height / frame.height) * fit.height}%`,
  };
}

export function overlayPointStyle(frame: { width: number; height: number }, x: number, y: number) {
  const fit = fitRect(frame.width, frame.height);
  return {
    left: `${fit.left + (x / frame.width) * fit.width}%`,
    top: `${fit.top + (y / frame.height) * fit.height}%`,
  };
}

export function sourceOverlayBoxStyle(
  frame: { width: number; height: number; semanticOffset?: { x: number; y: number } },
  box: [number, number, number, number],
) {
  const offset = frame.semanticOffset ?? { x: 0, y: 0 };
  return overlayBoxStyle(frame, [box[0] + offset.x, box[1] + offset.y, box[2], box[3]]);
}

export function qwenBox(
  frame: { width: number; height: number },
  bbox: [number, number, number, number],
): [number, number, number, number] {
  const [x1, y1, x2, y2] = bbox;
  return [
    (x1 / 1000) * frame.width,
    (y1 / 1000) * frame.height,
    ((x2 - x1) / 1000) * frame.width,
    ((y2 - y1) / 1000) * frame.height,
  ];
}

export function qwenPoint(frame: { width: number; height: number }, point: [number, number]) {
  return [(point[0] / 1000) * frame.width, (point[1] / 1000) * frame.height] as const;
}

export function maskToAlpha(encoded: string, width: number, height: number): ImageData | null {
  if (!encoded || width <= 0 || height <= 0) return null;
  const data = new Uint8ClampedArray(width * height * 4);
  const counts = encoded
    .split(",")
    .map((part) => Number(part))
    .filter((value) => Number.isFinite(value) && value >= 0);
  let offset = 0;
  let value = 0;
  for (const count of counts) {
    if (value) {
      for (let index = 0; index < count && offset + index < width * height; index++) {
        const pixel = (offset + index) * 4;
        data[pixel] = 116;
        data[pixel + 1] = 255;
        data[pixel + 2] = 216;
        data[pixel + 3] = 96;
      }
    }
    offset += count;
    value = value ? 0 : 1;
  }
  return new ImageData(data, width, height);
}
