import React from "react";
import { usePipelineStore } from "../stores/pipelineStore";
import { stageGroups } from "../utils/stage";
import { StatusIcon } from "./FieldControls";

export function StageNav() {
  const config = usePipelineStore((s) => s.config);
  const controls = usePipelineStore((s) => s.controls);
  const activeStageId = usePipelineStore((s) => s.activeStageId);
  const stageStatuses = usePipelineStore((s) => s.stageStatuses);
  const setActiveStageId = usePipelineStore((s) => s.setActiveStageId);

  const groups = stageGroups(config, controls);

  return React.createElement(
    "nav",
    { className: "stage-nav" },
    ...groups.map((g) =>
      React.createElement(
        "button",
        {
          key: g.id,
          className: `stage-nav-btn ${activeStageId === g.id ? "stage-nav-active" : ""}`,
          "data-stage-id": g.id,
          type: "button",
          onClick: () => setActiveStageId(activeStageId === g.id ? null : g.id),
        },
        React.createElement(StatusIcon, {
          status: stageStatuses[g.id] ?? "idle",
          included: g.included,
        }),
        React.createElement("span", null, g.label),
      ),
    ),
  );
}
