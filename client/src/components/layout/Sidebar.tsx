import React from "react";
import { StageNav } from "../StageNav";
import { StageControls } from "../StageControls";

export function PipelineNav() {
  return React.createElement(
    "aside",
    { className: "pipeline-nav-panel" },
    React.createElement("h2", null, "Pipeline"),
    React.createElement("div", { className: "sidebar-section" }, React.createElement(StageNav, null)),
  );
}

export function SettingsPanel() {
  return React.createElement(
    "aside",
    { className: "settings-panel" },
    React.createElement("h2", null, "Settings"),
    React.createElement("div", { className: "sidebar-controls" }, React.createElement(StageControls, null)),
  );
}
