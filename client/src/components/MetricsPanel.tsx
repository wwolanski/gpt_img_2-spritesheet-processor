import React from "react";
import { usePipelineStore } from "../stores/pipelineStore";
import { stabilizationRows } from "../services/stabilization";

export function MetricsPanel() {
  const current = usePipelineStore((s) => s.current);

  if (!current) {
    return React.createElement(
      "div",
      { className: "panel" },
      React.createElement("p", { className: "empty-copy" }, "Brak metryk."),
    );
  }

  const { flowRatio, stableRatio } = stabilizationRows(current);

  return React.createElement(
    "div",
    { className: "panel" },
    React.createElement("h2", null, "Metrics"),
    React.createElement(
      "dl",
      { className: "metric-list" },
      metricRow("score", String(current.metrics.score)),
      metricRow("border leak", String(current.metrics.border_leak_ratio)),
      metricRow("green spill", String(current.metrics.green_spill_ratio)),
      metricRow("edge alpha", String(current.metrics.edge_alpha_ratio)),
      metricRow("tiny comps", String(current.metrics.tiny_component_count)),
      metricRow("opaque cover", String(current.metrics.opaque_coverage)),
      flowRatio !== null ? metricRow("flow blend", flowRatio) : null,
      stableRatio !== null ? metricRow("stable px", stableRatio) : null,
    ),
  );
}

function metricRow(label: string, value: string) {
  return React.createElement(
    "div",
    null,
    React.createElement("dt", null, label),
    React.createElement("dd", null, value),
  );
}
