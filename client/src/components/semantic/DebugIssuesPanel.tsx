import React from "react";
import { InfoTip } from "./InfoTip";
import type { SemanticIssue } from "../../types/pipeline";

export function DebugIssuesPanel({
  issues,
  issueFilter,
  setIssueFilter,
  setActivePartId,
  setFrameIndex,
  audit,
}: {
  issues: SemanticIssue[];
  issueFilter: string;
  setIssueFilter: (filter: string) => void;
  setActivePartId: (id: string | null) => void;
  setFrameIndex: (index: number) => void;
  audit: Record<string, unknown>;
}) {
  const filteredIssues = issues.filter(
    (issue) => issueFilter === "all" || issue.severity === issueFilter || issue.type === issueFilter,
  );
  const issueTypes = Array.from(new Set(issues.map((issue) => issue.type))).sort();

  return React.createElement(
    "div",
    { className: "panel debug-issues-panel" },
    React.createElement(
      "div",
      { className: "debug-panel-head" },
      React.createElement(
        "h3",
        null,
        "semanticIssues ",
        React.createElement(InfoTip, {
          text: "Structured raport backendu. Kliknięcie issue ustawia part/frame, żeby szybko dojść do miejsca błędu.",
        }),
      ),
      React.createElement(
        "select",
        {
          value: issueFilter,
          onChange: (event: React.ChangeEvent<HTMLSelectElement>) => setIssueFilter(event.currentTarget.value),
        },
        React.createElement("option", { value: "all" }, "all"),
        React.createElement("option", { value: "review" }, "review"),
        React.createElement("option", { value: "warn" }, "warn"),
        issueTypes.map((type) => React.createElement("option", { key: type, value: type }, type)),
      ),
    ),
    filteredIssues.length
      ? React.createElement(
          "div",
          { className: "debug-issue-list" },
          filteredIssues.map((issue, index) =>
            React.createElement(
              "button",
              {
                key: `${issue.partId ?? "global"}-${issue.frame ?? "run"}-${issue.type}-${index}`,
                type: "button",
                className: `debug-issue debug-issue-${issue.severity}`,
                onClick: () => {
                  if (issue.partId) setActivePartId(issue.partId);
                  if (typeof issue.frame === "number") setFrameIndex(issue.frame);
                },
              },
              React.createElement("strong", null, issue.type),
              React.createElement(
                "span",
                null,
                [issue.partId, typeof issue.frame === "number" ? `frame ${issue.frame}` : null, issue.severity]
                  .filter(Boolean)
                  .join(" / "),
              ),
              React.createElement("small", null, issue.message),
            ),
          ),
        )
      : React.createElement("p", { className: "muted-copy" }, "No structured issues"),
    React.createElement("pre", { className: "debug-audit" }, JSON.stringify(audit ?? {}, null, 2)),
  );
}
