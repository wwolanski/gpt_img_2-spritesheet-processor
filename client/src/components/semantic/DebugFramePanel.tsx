import React from "react";
import { previewUrl } from "../../api/urls";
import { FrameStepper } from "../FrameStepper";
import { editBox } from "../../utils/edit";
import {
  fitRect,
  overlayBoxStyle,
  overlayPointStyle,
  sourceOverlayBoxStyle,
  qwenBox,
  qwenPoint,
  maskToAlpha,
} from "../../utils/canvas";
import { FRAME_VIEWS } from "../../constants/semantic";
import { InfoTip } from "./InfoTip";
import type { SemanticDebugFrame, SemanticEdit, SemanticGrounding, ProcessResponse } from "../../types/pipeline";

function MaskCanvas({
  encoded,
  frame,
  className,
  sourceSized = false,
}: {
  encoded?: string;
  frame: {
    width: number;
    height: number;
    sourceWidth?: number;
    sourceHeight?: number;
    semanticOffset?: { x: number; y: number };
  };
  className: string;
  sourceSized?: boolean;
}) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const maskWidth = sourceSized ? (frame.sourceWidth ?? frame.width) : frame.width;
  const maskHeight = sourceSized ? (frame.sourceHeight ?? frame.height) : frame.height;
  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    canvas.width = maskWidth;
    canvas.height = maskHeight;
    ctx.clearRect(0, 0, maskWidth, maskHeight);
    const imageData = maskToAlpha(encoded ?? "", maskWidth, maskHeight);
    if (imageData) ctx.putImageData(imageData, 0, 0);
  }, [encoded, maskWidth, maskHeight]);
  const fit = fitRect(frame.width, frame.height);
  const offset = sourceSized ? (frame.semanticOffset ?? { x: 0, y: 0 }) : { x: 0, y: 0 };
  return React.createElement("canvas", {
    ref: canvasRef,
    className,
    style: {
      left: `${fit.left + (offset.x / frame.width) * fit.width}%`,
      top: `${fit.top + (offset.y / frame.height) * fit.height}%`,
      width: `${(maskWidth / frame.width) * fit.width}%`,
      height: `${(maskHeight / frame.height) * fit.height}%`,
    },
  });
}

export function DebugFramePanel({
  debugFrame,
  current,
  frameIndexes,
  frameIndex,
  setFrameIndex,
  overlayLayers,
  toggleOverlayLayer,
  activeQwenGrounding,
  activeGroundingEdits,
  activeSam3Edits,
  activeRawMask,
  activeValidatedMask,
  activeTrackBox,
  activeMaskStatus,
  activeFrameMetric,
  postprocessLabel,
}: {
  debugFrame: SemanticDebugFrame | undefined;
  current: ProcessResponse | undefined;
  frameIndexes: number[];
  frameIndex: number;
  setFrameIndex: (index: number) => void;
  overlayLayers: { qwen: boolean; sam: boolean; track: boolean; mask: boolean };
  toggleOverlayLayer: (key: keyof { qwen: boolean; sam: boolean; track: boolean; mask: boolean }) => void;
  activeQwenGrounding: SemanticGrounding[];
  activeGroundingEdits: SemanticEdit[];
  activeSam3Edits: SemanticEdit[];
  activeRawMask: string | undefined;
  activeValidatedMask: string | undefined;
  activeTrackBox: { x: number; y: number; width: number; height: number } | null;
  activeMaskStatus?: string;
  activeFrameMetric?: { iouPrev?: number; areaRatio?: number; componentCount?: number };
  postprocessLabel: string;
}) {
  return React.createElement(
    "div",
    { className: "panel debug-frame-panel" },
    React.createElement(
      "div",
      { className: "debug-panel-head" },
      React.createElement(
        "h3",
        null,
        "Frame inputs ",
        React.createElement(InfoTip, {
          text: "Cztery widoki tej samej klatki. Najważniejszy dla modeli jest sam_rgb_frame: to on trafia do Qwen3 i SAM3.",
        }),
      ),
      React.createElement(FrameStepper, { frameIndexes, value: frameIndex, onChange: setFrameIndex }),
    ),
    debugFrame && current
      ? React.createElement(
          "div",
          { className: "debug-image-grid" },
          FRAME_VIEWS.map((view) =>
            React.createElement(
              "figure",
              {
                key: view.key,
                className: `debug-image-card ${view.key === "samRgb" ? "debug-image-card-primary" : ""}`,
              },
              React.createElement(
                "div",
                { className: "debug-image-media" },
                React.createElement("img", {
                  src: previewUrl(current.previewId, debugFrame.files[view.key]),
                  alt: view.label,
                }),
                view.key === "samRgb"
                  ? React.createElement(
                      "div",
                      { className: "semantic-overlay", "aria-hidden": true },
                      overlayLayers.mask
                        ? React.createElement(MaskCanvas, {
                            encoded: activeRawMask,
                            frame: debugFrame,
                            className: "semantic-mask semantic-mask-raw",
                            sourceSized: true,
                          })
                        : null,
                      overlayLayers.mask
                        ? React.createElement(MaskCanvas, {
                            encoded: activeValidatedMask,
                            frame: debugFrame,
                            className: "semantic-mask semantic-mask-validated",
                            sourceSized: true,
                          })
                        : null,
                      overlayLayers.qwen
                        ? activeQwenGrounding.map((hint, index) => {
                            const box = qwenBox(debugFrame, hint.bbox_2d);
                            const [px, py] = qwenPoint(debugFrame, hint.point_2d);
                            return React.createElement(
                              React.Fragment,
                              { key: `${hint.frame}-${index}` },
                              React.createElement("span", {
                                className: "overlay-box overlay-box-qwen",
                                style: overlayBoxStyle(debugFrame, box),
                              }),
                              React.createElement("span", {
                                className: "overlay-point overlay-point-qwen",
                                style: overlayPointStyle(debugFrame, px, py),
                              }),
                            );
                          })
                        : null,
                      overlayLayers.sam
                        ? activeSam3Edits.map((edit, index) => {
                            if (edit.type === "bbox") {
                              const box = editBox(edit);
                              return box
                                ? React.createElement("span", {
                                    key: `edit-${index}`,
                                    className: "overlay-box overlay-box-sam",
                                    style: overlayBoxStyle(debugFrame, box),
                                  })
                                : null;
                            }
                            return React.createElement("span", {
                              key: `edit-${index}`,
                              className: `overlay-point ${edit.type === "negative_point" ? "overlay-point-negative" : "overlay-point-sam"}`,
                              style: overlayPointStyle(debugFrame, edit.x ?? 0, edit.y ?? 0),
                            });
                          })
                        : null,
                      overlayLayers.track && activeTrackBox
                        ? React.createElement("span", {
                            className: "overlay-box overlay-box-track",
                            style: sourceOverlayBoxStyle(debugFrame, [
                              activeTrackBox.x,
                              activeTrackBox.y,
                              activeTrackBox.width,
                              activeTrackBox.height,
                            ]),
                          })
                        : null,
                    )
                  : null,
              ),
              view.key === "samRgb"
                ? React.createElement(
                    "div",
                    { className: "semantic-overlay-legend" },
                    React.createElement(
                      "label",
                      null,
                      React.createElement("input", {
                        type: "checkbox",
                        checked: overlayLayers.qwen,
                        onChange: () => toggleOverlayLayer("qwen"),
                      }),
                      React.createElement("i", { className: "legend-swatch legend-qwen" }),
                      `Qwen raw hint: ${activeQwenGrounding.length}`,
                    ),
                    React.createElement(
                      "label",
                      null,
                      React.createElement("input", {
                        type: "checkbox",
                        checked: overlayLayers.sam,
                        onChange: () => toggleOverlayLayer("sam"),
                      }),
                      React.createElement("i", { className: "legend-swatch legend-sam" }),
                      `Semantic grounding edits: ${activeGroundingEdits.length}`,
                    ),
                    React.createElement(
                      "label",
                      null,
                      React.createElement("input", {
                        type: "checkbox",
                        checked: overlayLayers.track,
                        onChange: () => toggleOverlayLayer("track"),
                      }),
                      React.createElement("i", { className: "legend-swatch legend-track" }),
                      `SAM3 mask bbox: ${activeTrackBox ? 1 : 0}`,
                    ),
                    React.createElement(
                      "label",
                      null,
                      React.createElement("input", {
                        type: "checkbox",
                        checked: overlayLayers.mask,
                        onChange: () => toggleOverlayLayer("mask"),
                      }),
                      React.createElement("i", { className: "legend-swatch legend-mask" }),
                      "mask fill",
                    ),
                    React.createElement("span", { className: "legend-mode" }, postprocessLabel),
                    activeMaskStatus
                      ? React.createElement(
                          "span",
                          { className: `legend-mode legend-status legend-status-${activeMaskStatus}` },
                          `${activeMaskStatus} / iouPrev ${activeFrameMetric?.iouPrev ?? "-"} / area ${activeFrameMetric?.areaRatio ?? "-"}`,
                        )
                      : null,
                  )
                : null,
              React.createElement(
                "figcaption",
                null,
                React.createElement(
                  "span",
                  null,
                  React.createElement("strong", null, view.label),
                  React.createElement("small", null, view.route),
                ),
                React.createElement(InfoTip, { text: view.hint }),
              ),
            ),
          ),
        )
      : React.createElement("p", { className: "muted-copy" }, "Uruchom preview, żeby zobaczyć debug frames."),
  );
}
