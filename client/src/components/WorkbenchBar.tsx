import React from "react";
import { usePipelineStore } from "../stores/pipelineStore";
import { SelectField, Spinner, type SelectOption } from "./FieldControls";
import type { PipelineAction } from "../types/actions";

export function WorkbenchBar({ onAction }: { onAction: (action: PipelineAction) => void }) {
  const config = usePipelineStore((s) => s.config);
  const sources = usePipelineStore((s) => s.sources);
  const controls = usePipelineStore((s) => s.controls);
  const currentResult = usePipelineStore((s) => s.current);
  const loading = usePipelineStore((s) => s.loading);
  const showBoxes = usePipelineStore((s) => s.showBoxes);
  const status = usePipelineStore((s) => s.status);
  const exportStatus = usePipelineStore((s) => s.exportStatus);
  const setControl = usePipelineStore((s) => s.setControl);
  const setShowBoxes = usePipelineStore((s) => s.setShowBoxes);

  const sourceOptions: SelectOption[] = sources.map((source) => ({
    value: source.name,
    label: source.name,
  }));
  const profileOptions: SelectOption[] = (config?.profiles ?? []).map((profile) => ({
    value: profile,
    label: profile,
  }));
  const pipelineOptions: SelectOption[] = (config?.pipelines ?? []).map((pipeline) => ({
    value: pipeline.id,
    label: pipeline.enabled ? pipeline.label : `${pipeline.label} (unavailable)`,
    disabled: !pipeline.enabled,
  }));

  return (
    <div className="panel workbench-bar">
      <div className="workbench-inputs">
        <SelectField field="source" label="Source" options={sourceOptions} />
        <SelectField field="profile" label="Config profile" options={profileOptions} />
        <SelectField field="pipelineId" label="Pipeline" options={pipelineOptions} />
        <label className="field">
          <span>Export slug</span>
          <input
            data-field="exportSlug"
            type="text"
            value={controls.exportSlug}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setControl("exportSlug", e.target.value)}
          />
        </label>
      </div>
      <div className="workbench-actions">
        <button className="primary-btn" onClick={() => onAction("process")} disabled={loading}>
          Render
        </button>
        <button className="ghost-btn" onClick={() => onAction("compare")} disabled={loading}>
          Compare
        </button>
        <button className="ghost-btn" onClick={() => onAction("compare-all")} disabled={loading}>
          Matrix
        </button>
        <button className="success-btn" onClick={() => onAction("export")} disabled={!currentResult}>
          Export
        </button>
        <label className="checkbox">
          <input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} />
          <span>Boxes</span>
        </label>
      </div>
      <p className="status-line">
        <Spinner active={loading} />
        {status}
      </p>
      <p className="status-line status-line-export">{exportStatus}</p>
    </div>
  );
}
