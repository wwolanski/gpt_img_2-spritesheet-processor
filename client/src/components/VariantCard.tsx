import React from "react";
import type { VariantPreview } from "../types/pipeline";
import { Spinner } from "./FieldControls";

export function VariantCard({
  variant,
  isActive,
  onClick,
}: {
  variant: VariantPreview;
  isActive: boolean;
  onClick: () => void;
}) {
  const result = variant.result;

  return React.createElement(
    "button",
    {
      className: `variant-card ${isActive ? "variant-card-active" : ""}`,
      disabled: !result,
      onClick,
    },
    React.createElement(
      "div",
      { className: "variant-card-head" },
      React.createElement("strong", null, variant.label),
      React.createElement(
        "span",
        null,
        variant.status === "running" ? React.createElement(Spinner, { active: true }) : (result?.metrics.score ?? "!"),
      ),
    ),
    React.createElement("p", null, variant.pipelineId),
    React.createElement(
      "small",
      null,
      result
        ? `spill ${result.metrics.green_spill_ratio}, edge ${result.metrics.edge_alpha_ratio}, frames ${result.frames.length}`
        : (variant.error ?? "render pending"),
    ),
  );
}
