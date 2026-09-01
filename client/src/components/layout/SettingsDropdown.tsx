import React from "react";
import { usePipelineStore } from "../../stores/pipelineStore";

export function SettingsDropdown() {
  const [open, setOpen] = React.useState(false);
  const autoRunEnabled = usePipelineStore((s) => s.autoRunEnabled);
  const setAutoRunEnabled = usePipelineStore((s) => s.setAutoRunEnabled);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) {
      document.addEventListener("mousedown", onClick);
      return () => document.removeEventListener("mousedown", onClick);
    }
  }, [open]);

  return React.createElement(
    "div",
    { ref, className: "settings-dropdown" },
    React.createElement(
      "button",
      {
        type: "button",
        className: "settings-btn",
        title: "Settings",
        onClick: () => setOpen((v) => !v),
      },
      React.createElement(
        "svg",
        {
          width: 18,
          height: 18,
          viewBox: "0 0 24 24",
          fill: "none",
          stroke: "currentColor",
          strokeWidth: 2,
          strokeLinecap: "round",
          strokeLinejoin: "round",
        },
        React.createElement("circle", { cx: 12, cy: 12, r: 3 }),
        React.createElement("path", {
          d: "M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z",
        }),
      ),
    ),
    open &&
      React.createElement(
        "div",
        { className: "settings-menu" },
        React.createElement(
          "label",
          { className: "switch-field" },
          React.createElement("span", null, "Auto-render on change"),
          React.createElement("input", {
            type: "checkbox",
            checked: autoRunEnabled,
            onChange: (e: React.ChangeEvent<HTMLInputElement>) => setAutoRunEnabled(e.target.checked),
          }),
          React.createElement("strong", null, autoRunEnabled ? "ON" : "OFF"),
        ),
      ),
  );
}
