import React from "react";
import { usePipelineStore } from "../stores/pipelineStore";
import { VariantCard } from "./VariantCard";
import { MetricsPanel } from "./MetricsPanel";

export function VariantPanel() {
  const variants = usePipelineStore((s) => s.variants);
  const activeVariantId = usePipelineStore((s) => s.activeVariantId);
  const setCurrent = usePipelineStore((s) => s.setCurrent);
  const config = usePipelineStore((s) => s.config);

  return React.createElement(
    React.Fragment,
    null,
    React.createElement(
      "div",
      { className: "panel" },
      React.createElement("h2", null, "Variants"),
      React.createElement(
        "p",
        { className: "variant-copy" },
        "Uruchom compare, kliknij wariant, oceń preview animacji, dopiero potem export.",
      ),
      React.createElement(
        "div",
        { className: "variant-list" },
        variants.length > 0
          ? variants.map((v) =>
              React.createElement(VariantCard, {
                key: v.id,
                variant: v,
                isActive: v.id === activeVariantId,
                onClick: () => {
                  if (v.result) {
                    const label = config?.pipelines.find((p) => p.id === v.pipelineId)?.label ?? v.pipelineId;
                    setCurrent(v.result, label, v.controls);
                  }
                },
              }),
            )
          : React.createElement("p", { className: "empty-copy" }, "Brak porównania."),
      ),
    ),
    React.createElement(MetricsPanel, null),
  );
}
