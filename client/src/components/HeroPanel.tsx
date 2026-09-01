import React from "react";
import { usePipelineStore } from "../stores/pipelineStore";

export function HeroPanel() {
  const sources = usePipelineStore((s) => s.sources);
  const current = usePipelineStore((s) => s.current);

  return React.createElement(
    "section",
    { className: "hero-panel" },
    React.createElement(
      "div",
      null,
      React.createElement("p", { className: "eyebrow" }, "Asset Pipeline Workbench"),
      React.createElement("h1", null, "Multi-step chroma key. Auto frame split. Preview before write."),
      React.createElement(
        "p",
        { className: "hero-copy" },
        "Source + profile + pipeline. Każdy pipeline ma własne tweak values. Compare odpala enabled pipeline równolegle.",
      ),
    ),
    React.createElement(
      "div",
      { className: "hero-stats" },
      React.createElement("span", null, React.createElement("strong", null, String(sources.length)), " źródeł"),
      React.createElement(
        "span",
        null,
        React.createElement("strong", null, String(current?.frames.length ?? 0)),
        " klatek",
      ),
      React.createElement("span", null, React.createElement("strong", null, current?.metrics.score ?? "-"), " score"),
    ),
  );
}
