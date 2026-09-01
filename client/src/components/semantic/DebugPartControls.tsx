import React from "react";
import { MOBILITY, PERSISTENCE } from "../../constants/semantic";
import { InfoTip } from "./InfoTip";
import type { SemanticManualPart, SemanticPart } from "../../types/pipeline";

export function DebugPartControls({
  parts,
  activePart,
  setActivePartId,
  manualPart,
  upsertManualPart,
  removeManualPart,
  useDetectedParts,
  clearSemanticEdits,
  activeQwenGrounding,
  activeGroundingEdits,
  activeManualEdits,
  rawTrack,
  validatedTrack,
  frameIndex,
  controls,
}: {
  parts: SemanticPart[];
  activePart: SemanticPart | undefined;
  setActivePartId: (id: string | null) => void;
  manualPart: SemanticManualPart | undefined;
  upsertManualPart: (patch: Partial<SemanticManualPart>) => void;
  removeManualPart: () => void;
  useDetectedParts: () => void;
  clearSemanticEdits: () => void;
  activeQwenGrounding: { frame: number }[];
  activeGroundingEdits: { frame: number }[];
  activeManualEdits: { frame: number }[];
  rawTrack: { presence?: boolean[] } | undefined;
  validatedTrack:
    | {
        presence?: boolean[];
        maskStatuses?: string[];
        trackSummary?: {
          accepted: number;
          repaired: number;
          missing: number;
          rejected: number;
          areaJitter: number;
          centroidJitter: number;
          loopIoU: number;
        };
      }
    | undefined;
  frameIndex: number;
  controls: { semanticEdits: unknown[] };
}) {
  return React.createElement(
    "div",
    { className: "panel debug-controls-panel" },
    React.createElement(
      "h3",
      null,
      "Part controls ",
      React.createElement(InfoTip, {
        text: "Tu zmieniasz kontrakt części: prompt trafia potem do SAM3 text prompt; mobility/persistence sterują walidacją i warningami backendu.",
      }),
    ),
    parts.length
      ? React.createElement(
          "div",
          { className: "debug-part-list" },
          parts.map((part) =>
            React.createElement(
              "button",
              {
                key: part.id,
                type: "button",
                className: `part-row ${activePart?.id === part.id ? "part-row-active" : ""}`,
                onClick: () => setActivePartId(part.id),
              },
              React.createElement("span", { className: "part-swatch", style: { background: part.color } }),
              React.createElement(
                "span",
                { className: "part-main" },
                React.createElement("strong", null, part.label),
                React.createElement(
                  "span",
                  null,
                  `${part.presence.filter(Boolean).length}/${part.presence.length} / conf ${part.confidence.toFixed(2)}`,
                  part.trackSummary
                    ? ` / repaired ${part.trackSummary.repaired} / rejected ${part.trackSummary.rejected}`
                    : "",
                ),
              ),
            ),
          ),
        )
      : React.createElement("p", { className: "muted-copy" }, "No parts"),
    manualPart
      ? React.createElement(
          "div",
          { className: "debug-edit-form" },
          React.createElement(
            "div",
            { className: "debug-track-summary" },
            React.createElement("span", null, `Qwen hints: ${activeQwenGrounding.length}`),
            React.createElement("span", null, `Grounding edits: ${activeGroundingEdits.length}`),
            React.createElement("span", null, `Manual/editor edits: ${activeManualEdits.length}`),
            React.createElement("span", null, `raw mask: ${rawTrack?.presence?.[frameIndex] ? "yes" : "no"}`),
            React.createElement(
              "span",
              null,
              `validated mask: ${validatedTrack?.presence?.[frameIndex] ? "yes" : "no"}`,
            ),
            React.createElement("span", null, `status: ${validatedTrack?.maskStatuses?.[frameIndex] ?? "-"}`),
            validatedTrack?.trackSummary
              ? React.createElement(
                  "span",
                  null,
                  `jitter area ${validatedTrack.trackSummary.areaJitter} / centroid ${validatedTrack.trackSummary.centroidJitter} / loop ${validatedTrack.trackSummary.loopIoU}`,
                )
              : null,
          ),
          React.createElement(
            "label",
            null,
            "prompt",
            React.createElement("input", {
              value: manualPart.prompt,
              onChange: (event: React.ChangeEvent<HTMLInputElement>) =>
                upsertManualPart({ prompt: event.currentTarget.value }),
            }),
          ),
          React.createElement(
            "label",
            null,
            "mobility",
            React.createElement(
              "select",
              {
                value: manualPart.mobility,
                onChange: (event: React.ChangeEvent<HTMLSelectElement>) =>
                  upsertManualPart({ mobility: event.currentTarget.value as SemanticManualPart["mobility"] }),
              },
              MOBILITY.map((value) => React.createElement("option", { key: value, value }, value)),
            ),
          ),
          React.createElement(
            "label",
            null,
            "persistence",
            React.createElement(
              "select",
              {
                value: manualPart.persistence,
                onChange: (event: React.ChangeEvent<HTMLSelectElement>) =>
                  upsertManualPart({ persistence: event.currentTarget.value as SemanticManualPart["persistence"] }),
              },
              PERSISTENCE.map((value) => React.createElement("option", { key: value, value }, value)),
            ),
          ),
          React.createElement(
            "div",
            { className: "debug-button-row" },
            React.createElement(
              "button",
              { type: "button", className: "compact-btn", onClick: useDetectedParts },
              "Use detected",
            ),
            React.createElement(
              "button",
              { type: "button", className: "compact-btn", onClick: removeManualPart },
              "Disable part",
            ),
            React.createElement(
              "button",
              { type: "button", className: "compact-btn", onClick: clearSemanticEdits },
              `Clear edits (${controls.semanticEdits.length})`,
            ),
          ),
        )
      : null,
  );
}
