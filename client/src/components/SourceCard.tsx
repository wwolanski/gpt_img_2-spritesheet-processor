import React from "react";
import { usePipelineStore } from "../stores/pipelineStore";
import { sourceUrl } from "../api/urls";

export function SourceCard() {
  const source = usePipelineStore((s) => s.controls.source);

  const src = source ? sourceUrl(source) : null;

  return React.createElement(
    "div",
    { className: "source-card" },
    React.createElement("h3", null, "Source"),
    src
      ? React.createElement("img", {
          className: "preview-image",
          src,
          alt: "source",
        })
      : React.createElement("p", { className: "empty-copy" }, "Brak source."),
  );
}
