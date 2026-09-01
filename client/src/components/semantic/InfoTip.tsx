import React from "react";

export function InfoTip({ text }: { text: string }) {
  return React.createElement(
    "span",
    { className: "info-tip", tabIndex: 0, "aria-label": text },
    "i",
    React.createElement("span", { className: "info-tip-popover" }, text),
  );
}
