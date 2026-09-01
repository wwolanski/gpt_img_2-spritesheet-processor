import React from "react";
import { usePipelineStore } from "../stores/pipelineStore";
import type { SemanticManualPart } from "../types/pipeline";

const MOBILITY = new Set(["static", "low", "medium", "high", "accessory"]);
const PERSISTENCE = new Set(["always", "occasional"]);

function parseManualParts(value: string): SemanticManualPart[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [idRaw, labelRaw, promptRaw, mobilityRaw, persistenceRaw] = line.split("|").map((part) => part.trim());
      const id = (idRaw || labelRaw || "")
        .toLowerCase()
        .replace(/[^a-z0-9_]+/g, "_")
        .replace(/^_|_$/g, "");
      const label = labelRaw || id;
      const mobility = MOBILITY.has(mobilityRaw) ? mobilityRaw : "medium";
      const persistence = PERSISTENCE.has(persistenceRaw) ? persistenceRaw : "always";
      return {
        id,
        label,
        prompt: promptRaw || label,
        mobility: mobility as SemanticManualPart["mobility"],
        persistence: persistence as SemanticManualPart["persistence"],
      };
    })
    .filter((part) => part.id);
}

export function PartInspector() {
  const current = usePipelineStore((s) => s.current);
  const showParts = usePipelineStore((s) => s.showParts);
  const setShowParts = usePipelineStore((s) => s.setShowParts);
  const activePartId = usePipelineStore((s) => s.activePartId);
  const setActivePartId = usePipelineStore((s) => s.setActivePartId);
  const controls = usePipelineStore((s) => s.controls);
  const setSemanticEditTool = usePipelineStore((s) => s.setSemanticEditTool);
  const clearSemanticEdits = usePipelineStore((s) => s.clearSemanticEdits);
  const setSemanticManualParts = usePipelineStore((s) => s.setSemanticManualParts);
  const [manualText, setManualText] = React.useState("");
  const semantic = current?.semantic;
  const parts = semantic?.parts ?? [];
  const issueCount = semantic?.semanticIssues?.length ?? 0;

  return React.createElement(
    "section",
    { className: "part-inspector" },
    React.createElement(
      "div",
      { className: "part-inspector-head" },
      React.createElement("h3", null, "Parts"),
      React.createElement(
        "label",
        { className: "toggle-row" },
        React.createElement("input", {
          type: "checkbox",
          checked: showParts,
          onChange: (event) => setShowParts(event.currentTarget.checked),
        }),
        React.createElement("span", null, "Show parts"),
      ),
    ),
    React.createElement(
      "div",
      { className: "semantic-tools" },
      React.createElement(
        "div",
        { className: "segmented-control" },
        React.createElement(
          "button",
          {
            type: "button",
            className: controls.semanticEditTool === "positive_point" ? "segmented-active" : "",
            onClick: () => setSemanticEditTool("positive_point"),
          },
          "+ point",
        ),
        React.createElement(
          "button",
          {
            type: "button",
            className: controls.semanticEditTool === "negative_point" ? "segmented-active" : "",
            onClick: () => setSemanticEditTool("negative_point"),
          },
          "- point",
        ),
      ),
      React.createElement("span", { className: "edit-count" }, `${controls.semanticEdits.length} edits`),
      React.createElement("button", { type: "button", className: "compact-btn", onClick: clearSemanticEdits }, "Clear"),
    ),
    semantic
      ? React.createElement(
          "div",
          { className: "semantic-summary" },
          React.createElement("span", null, "enabled ", React.createElement("strong", null, String(semantic.enabled))),
          React.createElement(
            "span",
            null,
            "model ",
            React.createElement("strong", null, semantic.maskModel ?? "sam3"),
          ),
          React.createElement(
            "span",
            null,
            "confidence ",
            React.createElement("strong", null, semantic.metrics.semantic_confidence_min),
          ),
          React.createElement(
            "span",
            null,
            "review ",
            React.createElement("strong", null, String(semantic.metrics.manual_review_required)),
          ),
          React.createElement("span", null, "issues ", React.createElement("strong", null, issueCount)),
        )
      : React.createElement("p", { className: "muted-copy" }, "No semantic metadata"),
    parts.length > 0
      ? React.createElement(
          "div",
          { className: "part-list" },
          parts.map((part) =>
            React.createElement(
              "button",
              {
                key: part.id,
                type: "button",
                className: `part-row ${activePartId === part.id ? "part-row-active" : ""}`,
                onClick: () => setActivePartId(activePartId === part.id ? null : part.id),
              },
              React.createElement("span", { className: "part-swatch", style: { background: part.color } }),
              React.createElement(
                "span",
                { className: "part-main" },
                React.createElement("strong", null, part.label),
                React.createElement("span", null, `${part.mobility} / ${part.persistence}`),
              ),
              React.createElement(
                "span",
                { className: "part-presence" },
                `${part.presence.filter(Boolean).length}/${part.presence.length}`,
              ),
              part.warnings.length > 0
                ? React.createElement("span", { className: "part-warning" }, String(part.warnings.length))
                : null,
            ),
          ),
        )
      : React.createElement("p", { className: "muted-copy" }, semantic?.warnings?.join("; ") || "No parts"),
    React.createElement(
      "div",
      { className: "manual-parts" },
      React.createElement("textarea", {
        value: manualText,
        onChange: (event: React.ChangeEvent<HTMLTextAreaElement>) => setManualText(event.currentTarget.value),
        placeholder: "id|label|prompt|mobility|persistence",
      }),
      React.createElement(
        "button",
        {
          type: "button",
          className: "compact-btn",
          onClick: () => setSemanticManualParts(parseManualParts(manualText)),
        },
        `Use manual parts (${controls.semanticManualParts.length})`,
      ),
    ),
  );
}
