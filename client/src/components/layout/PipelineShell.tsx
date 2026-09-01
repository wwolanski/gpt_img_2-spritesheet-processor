import React from "react";
import { HeroPanel } from "../HeroPanel";
import { PipelineNav, SettingsPanel } from "./Sidebar";
import { PreviewPanel } from "../PreviewPanel";
import { VariantPanel } from "../VariantPanel";
import { SemanticDebugWorkspace } from "../SemanticDebugWorkspace";
import { SemanticMaskEditor } from "../SemanticMaskEditor";
import { SettingsDropdown } from "./SettingsDropdown";
import type { PipelineAction } from "../../types/actions";

export function PipelineShell({ onAction }: { onAction: (action: PipelineAction) => void }) {
  const viewFromHash = () =>
    window.location.hash === "#/semantic-debug"
      ? "debug"
      : window.location.hash === "#/semantic-editor"
        ? "editor"
        : "workbench";
  const [view, setView] = React.useState<"workbench" | "debug" | "editor">(viewFromHash);

  React.useEffect(() => {
    const handleHash = () => setView(viewFromHash());
    window.addEventListener("hashchange", handleHash);
    return () => window.removeEventListener("hashchange", handleHash);
  }, []);

  const setHash = (next: "workbench" | "debug" | "editor") => {
    window.location.hash = next === "debug" ? "/semantic-debug" : next === "editor" ? "/semantic-editor" : "/";
    setView(next);
  };

  return (
    <div className="pipeline-shell">
      <HeroPanel />
      <nav className="top-view-nav">
        <div className="top-view-tabs">
          <button
            type="button"
            className={view === "workbench" ? "top-view-active" : ""}
            onClick={() => setHash("workbench")}
          >
            Workbench
          </button>
          <button type="button" className={view === "debug" ? "top-view-active" : ""} onClick={() => setHash("debug")}>
            Semantic debug
          </button>
          <button
            type="button"
            className={view === "editor" ? "top-view-active" : ""}
            onClick={() => setHash("editor")}
          >
            Semantic &amp; Mask editor
          </button>
        </div>
        <SettingsDropdown />
      </nav>
      {view === "debug" ? (
        <SemanticDebugWorkspace onAction={onAction} />
      ) : view === "editor" ? (
        <SemanticMaskEditor onAction={onAction} />
      ) : (
        <>
          <PipelineNav />
          <div className="pipeline-grid">
            <SettingsPanel />
            <PreviewPanel onAction={onAction} />
            <aside className="variant-panel">
              <VariantPanel />
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
