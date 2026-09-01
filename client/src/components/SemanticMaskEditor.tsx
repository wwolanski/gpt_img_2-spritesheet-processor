import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePipelineStore } from "../stores/pipelineStore";
import { InfoTip } from "./semantic/InfoTip";
import { deleteSemanticPreset, fetchSemanticPresets, saveSemanticPreset } from "../api/pipeline";
import { SemanticEditorCanvas, type DragPoint } from "./semantic/SemanticEditorCanvas";
import type {
  SemanticDebugPartSpec,
  SemanticEdit,
  SemanticEditorPart,
  SemanticEditorPresetSettings,
  SemanticManualPart,
} from "../types/pipeline";
import { MOBILITY, PERSISTENCE } from "../constants/semantic";
import { editKey, clamp } from "../utils/edit";
import type { PipelineAction } from "../types/actions";
import {
  cloneSemanticEdit as cloneEdit,
  cloneSemanticEditorPart as clonePart,
  editBoxRaw,
  editSpace,
  materializePresetSettings,
} from "../utils/semanticEditor";

const SEMANTIC_PRESETS_QUERY_KEY = ["pipeline", "semantic-presets"] as const;
const PART_COLORS = ["#FFB000", "#74FFD8", "#FF8D8D", "#B8D7FF", "#D8FF6A", "#D2AAFF"];
const DEFAULT_STABILIZE_SETTINGS = {
  enabled: true,
  repairEnabled: true,
  repairSearchScale: 1,
  patchLockStrength: 1,
  medianStrength: 1,
};

function adoptParts(parts: SemanticDebugPartSpec[], edits: SemanticEdit[]): SemanticEditorPart[] {
  return parts.map((part, index) => ({
    id: part.id,
    label: part.label,
    prompt: part.prompt || part.label,
    mobility: part.mobility,
    persistence: part.persistence,
    color: PART_COLORS[index % PART_COLORS.length],
    edits: edits.filter((edit) => edit.partId === part.id).map(cloneEdit),
  }));
}

function sanitizePart(part: SemanticEditorPart): SemanticEditorPart {
  const id = part.id
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return { ...part, id: id || part.id };
}

function makePart(baseIndex: number, existingParts: SemanticEditorPart[]): SemanticEditorPart {
  const existingIds = new Set(existingParts.map((part) => part.id));
  let ordinal = Math.max(1, baseIndex + 1);
  let id = `part_${ordinal}`;
  while (existingIds.has(id)) {
    ordinal += 1;
    id = `part_${ordinal}`;
  }
  return {
    id,
    label: `Part ${ordinal}`,
    prompt: `Part ${ordinal}`,
    mobility: "medium",
    persistence: "always",
    color: PART_COLORS[existingParts.length % PART_COLORS.length],
    stabilizeSettings: { ...DEFAULT_STABILIZE_SETTINGS },
    edits: [],
  };
}

function stabilizeSettings(part: SemanticEditorPart) {
  return { ...DEFAULT_STABILIZE_SETTINGS, ...(part.stabilizeSettings ?? {}) };
}

function buildPresetSettings(
  controls: { [key: string]: unknown },
  editorParts: SemanticEditorPart[],
): SemanticEditorPresetSettings {
  return {
    semanticInputMode: controls.semanticInputMode as SemanticEditorPresetSettings["semanticInputMode"],
    semanticGroundingMinConfidence: Number(controls.semanticGroundingMinConfidence ?? 0.35),
    semanticGroundingAlphaCutoff: Number(controls.semanticGroundingAlphaCutoff ?? 10),
    semanticGroundingDilationRadius: Number(controls.semanticGroundingDilationRadius ?? 2),
    semanticGroundingAllowFrameReassign: Boolean(controls.semanticGroundingAllowFrameReassign),
    semanticGroundingFrameMinScore: Number(controls.semanticGroundingFrameMinScore ?? 0.08),
    semanticGroundingProjectionMode:
      controls.semanticGroundingProjectionMode as SemanticEditorPresetSettings["semanticGroundingProjectionMode"],
    semanticGroundingExpandRatio: Number(controls.semanticGroundingExpandRatio ?? 0.08),
    semanticGroundingExpandMinPx: Number(controls.semanticGroundingExpandMinPx ?? 2),
    semanticGroundingEmitBbox: Boolean(controls.semanticGroundingEmitBbox),
    semanticGroundingEmitPositivePoint: Boolean(controls.semanticGroundingEmitPositivePoint),
    semanticMaskModel: String(controls.semanticMaskModel ?? "sam3"),
    semanticEditorParts: editorParts.map(clonePart),
  };
}

export function SemanticMaskEditor({ onAction }: { onAction: (action: PipelineAction) => void }) {
  const queryClient = useQueryClient();
  const current = usePipelineStore((s) => s.current);
  const controls = usePipelineStore((s) => s.controls);
  const activePartId = usePipelineStore((s) => s.activePartId);
  const setActivePartId = usePipelineStore((s) => s.setActivePartId);
  const activeEditId = usePipelineStore((s) => s.activeEditId);
  const setActiveEditId = usePipelineStore((s) => s.setActiveEditId);
  const setSemanticEditorParts = usePipelineStore((s) => s.setSemanticEditorParts);
  const clearSemanticEditorPartsOverride = usePipelineStore((s) => s.clearSemanticEditorPartsOverride);
  const applySemanticPreset = usePipelineStore((s) => s.applySemanticPreset);
  const setStatus = usePipelineStore((s) => s.setStatus);
  const hasSemanticEditorPartsOverride = usePipelineStore((s) =>
    Object.prototype.hasOwnProperty.call(s.pipelineTweaks[s.controls.pipelineId] ?? {}, "semanticEditorParts"),
  );
  const [frameIndex, setFrameIndex] = React.useState(0);
  const canvasRef = React.useRef<HTMLDivElement | null>(null);
  const [canvasSize, setCanvasSize] = React.useState({ width: 1, height: 1 });
  const [dragPoint, setDragPoint] = React.useState<DragPoint | null>(null);
  const [showCopyModal, setShowCopyModal] = React.useState(false);
  const [selectedPresetName, setSelectedPresetName] = React.useState("");
  const [presetStatus, setPresetStatus] = React.useState("");

  const presetsQuery = useQuery({
    queryKey: SEMANTIC_PRESETS_QUERY_KEY,
    queryFn: fetchSemanticPresets,
    staleTime: Infinity,
  });

  const debug = current?.semanticDebug;
  const frames = debug?.frames ?? [];
  const frame = frames.find((item) => item.index === frameIndex) ?? frames[0];
  const sourceParts = (debug?.partSpecs ?? debug?.qwenGrounding ?? []) as SemanticDebugPartSpec[];
  const editorParts = hasSemanticEditorPartsOverride
    ? controls.semanticEditorParts
    : adoptParts(sourceParts, debug?.sam3Edits ?? []);
  const presets = presetsQuery.data?.presets ?? [];
  const selectedPreset = presets.find((preset) => preset.name === selectedPresetName) ?? null;
  const activePart = editorParts.find((part) => part.id === activePartId) ?? editorParts[0];
  const activeEdits = activePart?.edits.filter((edit) => edit.frame === frame?.index) ?? [];
  const frameIndexes = frames.map((item) => item.index);
  const scaleX = canvasSize.width / Math.max(1, frame?.width ?? 1);
  const scaleY = canvasSize.height / Math.max(1, frame?.height ?? 1);

  const savePresetMutation = useMutation({
    mutationFn: ({ name, settings }: { name: string; settings: SemanticEditorPresetSettings }) =>
      saveSemanticPreset(name, settings),
    onSuccess: (data) => {
      queryClient.setQueryData(SEMANTIC_PRESETS_QUERY_KEY, { presets: data.presets });
      setSelectedPresetName(data.preset.name);
      setPresetStatus(`Preset zapisany: ${data.preset.name}`);
      setStatus(`Semantic preset saved: ${data.preset.name}`);
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : String(error);
      setPresetStatus(`Nie udało się zapisać presetu: ${message}`);
    },
  });

  const deletePresetMutation = useMutation({
    mutationFn: (name: string) => deleteSemanticPreset(name),
    onSuccess: (data) => {
      queryClient.setQueryData(SEMANTIC_PRESETS_QUERY_KEY, { presets: data.presets });
      setSelectedPresetName(data.presets[0]?.name ?? "");
      setPresetStatus(`Preset usunięty: ${data.deleted}`);
      setStatus(`Semantic preset deleted: ${data.deleted}`);
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : String(error);
      setPresetStatus(`Nie udało się usunąć presetu: ${message}`);
    },
  });

  const presetBusy = savePresetMutation.isPending || deletePresetMutation.isPending;
  const presetQueryError =
    presetsQuery.error instanceof Error
      ? presetsQuery.error.message
      : presetsQuery.error
        ? String(presetsQuery.error)
        : "";

  React.useEffect(() => {
    if (frames.length === 0) return;
    if (!frames.some((item) => item.index === frameIndex)) {
      setFrameIndex(frames[0].index);
    }
  }, [frames, frameIndex]);

  React.useEffect(() => {
    const node = canvasRef.current;
    if (!node) return;
    const update = () => {
      const rect = node.getBoundingClientRect();
      setCanvasSize({ width: rect.width || 1, height: rect.height || 1 });
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, [frame?.width, frame?.height]);

  React.useEffect(() => {
    if (!dragPoint) return;
    const move = (event: PointerEvent) => {
      if (!canvasRef.current || !frame) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const x = clamp(((event.clientX - rect.left) / rect.width) * frame.width, 0, frame.width - 1);
      const y = clamp(((event.clientY - rect.top) / rect.height) * frame.height, 0, frame.height - 1);
      updateEdit(dragPoint.partId, dragPoint.editIndex, { x: Math.round(x), y: Math.round(y) });
    };
    const up = () => setDragPoint(null);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up, { once: true });
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [dragPoint, frame, editorParts]);

  React.useEffect(() => {
    if (presets.length === 0) {
      if (selectedPresetName) setSelectedPresetName("");
      return;
    }
    if (!presets.some((preset) => preset.name === selectedPresetName)) {
      setSelectedPresetName(presets[0].name);
    }
  }, [presets, selectedPresetName]);

  const commitParts = (parts: SemanticEditorPart[]) => {
    setSemanticEditorParts(
      parts.map((part) => {
        const sanitized = sanitizePart(part);
        return {
          ...sanitized,
          edits: sanitized.edits.map((edit) => {
            const editFrame = frames.find((item) => item.index === edit.frame);
            const nextEdit = { ...edit, partId: sanitized.id };
            return editFrame
              ? {
                  ...nextEdit,
                  space: editSpace(
                    editFrame,
                    current?.previewId ?? "",
                    frames.length,
                    current?.semanticDebug?.frameInterpolation?.factor ?? 1,
                  ),
                }
              : nextEdit;
          }),
        };
      }),
    );
  };

  const updatePart = (partId: string, patch: Partial<SemanticEditorPart>) => {
    const nextId =
      patch.id !== undefined
        ? sanitizePart({ ...(editorParts.find((part) => part.id === partId) ?? makePart(0, [])), ...patch }).id
        : partId;
    commitParts(editorParts.map((part) => (part.id === partId ? { ...part, ...patch } : part)));
    if (activePartId === partId && nextId !== partId) {
      setActivePartId(nextId);
    }
  };

  const updateStabilize = (partId: string, patch: Partial<NonNullable<SemanticEditorPart["stabilizeSettings"]>>) => {
    const part = editorParts.find((item) => item.id === partId);
    if (!part) return;
    updatePart(partId, {
      stabilizeSettings: {
        ...stabilizeSettings(part),
        ...patch,
      },
    });
  };

  const updateEdit = (partId: string, editIndex: number, patch: Partial<SemanticEdit>) => {
    commitParts(
      editorParts.map((part) => {
        if (part.id !== partId) return part;
        return {
          ...part,
          edits: part.edits.map((edit, index) => (index === editIndex ? { ...edit, ...patch } : edit)),
        };
      }),
    );
  };

  const removeEdit = (partId: string, editIndex: number) => {
    commitParts(
      editorParts.map((part) => {
        if (part.id !== partId) return part;
        return { ...part, edits: part.edits.filter((_, index) => index !== editIndex) };
      }),
    );
  };

  const addEdit = (type: SemanticEdit["type"]) => {
    if (!activePart || !frame) return;
    const previewId = current?.previewId ?? "";
    const next: SemanticEdit =
      type === "bbox"
        ? {
            frame: frame.index,
            partId: activePart.id,
            type,
            box: [frame.width * 0.25, frame.height * 0.25, frame.width * 0.75, frame.height * 0.75].map(Math.round),
            space: editSpace(frame, previewId, frames.length, current?.semanticDebug?.frameInterpolation?.factor ?? 1),
          }
        : {
            frame: frame.index,
            partId: activePart.id,
            type,
            x: Math.round(frame.width / 2),
            y: Math.round(frame.height / 2),
            space: editSpace(frame, previewId, frames.length, current?.semanticDebug?.frameInterpolation?.factor ?? 1),
          };
    const nextIndex = activePart.edits.length;
    updatePart(activePart.id, { edits: [...activePart.edits, next] });
    setActiveEditId(editKey(activePart.id, nextIndex));
  };

  const addPart = () => {
    const nextPart = makePart(editorParts.length, editorParts);
    commitParts([...editorParts, nextPart]);
    setActivePartId(nextPart.id);
    setActiveEditId(null);
  };

  const removePart = (partId: string) => {
    const currentIndex = editorParts.findIndex((part) => part.id === partId);
    if (currentIndex < 0) return;
    const nextParts = editorParts.filter((part) => part.id !== partId);
    commitParts(nextParts);
    if (activePartId === partId) {
      setActivePartId(nextParts[currentIndex]?.id ?? nextParts[currentIndex - 1]?.id ?? null);
      setActiveEditId(null);
    }
  };

  const resetFromCurrent = () => {
    commitParts(adoptParts(sourceParts, debug?.sam3Edits ?? []));
    if (sourceParts[0]) setActivePartId(sourceParts[0].id);
  };

  const clearOverrides = () => clearSemanticEditorPartsOverride();

  const applySelectedPreset = () => {
    if (!selectedPreset || !current) return;
    const materialized = materializePresetSettings(
      selectedPreset.settings,
      frames,
      current.previewId,
      current.semanticDebug?.frameInterpolation,
    );
    applySemanticPreset(materialized);
    setActivePartId(materialized.semanticEditorParts[0]?.id ?? null);
    setActiveEditId(null);
    setPresetStatus(`Preset nałożony: ${selectedPreset.name}`);
    setStatus(`Semantic preset applied: ${selectedPreset.name}`);
  };

  const saveCurrentPreset = () => {
    const suggestedName = selectedPreset?.name ?? `${current?.source ?? "sprite"} ${controls.pipelineId}`;
    const name = window.prompt("Nazwa presetu", suggestedName);
    if (name === null) return;
    const trimmed = name.trim();
    if (!trimmed) {
      setPresetStatus("Podaj nazwę presetu.");
      return;
    }
    const exists = presets.some((preset) => preset.name.toLowerCase() === trimmed.toLowerCase());
    if (exists && !window.confirm(`Nadpisać preset "${trimmed}"?`)) {
      return;
    }
    savePresetMutation.mutate({ name: trimmed, settings: buildPresetSettings(controls, editorParts) });
  };

  const deleteSelectedPreset = () => {
    if (!selectedPreset) return;
    if (!window.confirm(`Usunąć preset "${selectedPreset.name}"?`)) return;
    deletePresetMutation.mutate(selectedPreset.name);
  };

  const copyEditsToAllFrames = () => {
    if (!frame) return;
    commitParts(
      editorParts.map((part) => {
        const currentFrameEdits = part.edits.filter((edit) => edit.frame === frame.index);
        const cloned = frames
          .filter((f) => f.index !== frame.index)
          .flatMap((f) => currentFrameEdits.map((edit) => ({ ...edit, frame: f.index })));
        return { ...part, edits: [...currentFrameEdits, ...cloned] };
      }),
    );
    setShowCopyModal(false);
  };

  if (!current || !debug || !frame) {
    return (
      <main className="semantic-editor-page">
        <section className="panel semantic-editor-empty">
          <h2>Semantic & Mask editor</h2>
          <p>Uruchom semantic preview, żeby edytować wejście SAM3.</p>
          <button type="button" className="primary-btn" onClick={() => onAction("process")}>
            Render
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="semantic-editor-page">
      <section className="panel semantic-editor-toolbar">
        <div className="semantic-editor-toolbar-main">
          <h2>Semantic & Mask editor</h2>
          <p>
            {current.source} / {current.pipelineId} / sam_rgb_frame
          </p>
        </div>
        <div className="semantic-editor-toolbar-side">
          <div className="semantic-editor-preset-bar">
            <label className="semantic-editor-preset-picker">
              <span>Preset</span>
              <select
                value={selectedPresetName}
                onChange={(event) => setSelectedPresetName(event.currentTarget.value)}
                disabled={presetsQuery.isLoading || presetBusy}
              >
                {presets.length ? (
                  presets.map((preset) => (
                    <option key={preset.name} value={preset.name}>
                      {preset.name}
                    </option>
                  ))
                ) : (
                  <option value="">{presetsQuery.isLoading ? "Loading presets..." : "No saved presets"}</option>
                )}
              </select>
            </label>
            <button
              type="button"
              className="compact-btn"
              onClick={applySelectedPreset}
              disabled={!selectedPreset || presetBusy}
            >
              Apply preset
            </button>
            <button type="button" className="compact-btn" onClick={saveCurrentPreset} disabled={presetBusy}>
              Save preset
            </button>
            <button
              type="button"
              className="compact-btn"
              onClick={deleteSelectedPreset}
              disabled={!selectedPreset || presetBusy}
            >
              Delete preset
            </button>
          </div>
          {(presetStatus || presetQueryError || selectedPreset?.updatedAt) && (
            <p className="semantic-editor-preset-status">
              {presetQueryError || presetStatus || ""}
              {!presetQueryError && !presetStatus && selectedPreset?.updatedAt
                ? `Last update: ${new Date(selectedPreset.updatedAt).toLocaleString()}`
                : ""}
            </p>
          )}
          <div className="semantic-editor-actions">
            <button type="button" className="compact-btn" onClick={resetFromCurrent}>
              Apply current SAM3 inputs
            </button>
            <button type="button" className="compact-btn" onClick={clearOverrides}>
              Clear editor overrides ({hasSemanticEditorPartsOverride ? controls.semanticEditorParts.length : 0})
            </button>
            <button type="button" className="primary-btn" onClick={() => onAction("process")}>
              Rerun
            </button>
          </div>
        </div>
      </section>

      <section className="semantic-editor-grid">
        <aside className="panel semantic-editor-sidebar">
          <div className="debug-panel-head">
            <h3>Parts</h3>
            <div className="semantic-editor-part-actions">
              <button type="button" className="compact-btn" onClick={addPart}>
                Add part
              </button>
              <button
                type="button"
                className="compact-btn"
                onClick={() => activePart && removePart(activePart.id)}
                disabled={!activePart}
              >
                Delete
              </button>
            </div>
          </div>
          <div className="debug-part-list">
            {editorParts.map((part) => (
              <button
                key={part.id}
                type="button"
                className={`part-row ${activePart?.id === part.id ? "part-row-active" : ""}`}
                onClick={() => setActivePartId(part.id)}
              >
                <span className="part-swatch" style={{ background: part.color ?? "#74FFD8" }} />
                <span className="part-main">
                  <strong>{part.label}</strong>
                  <span>{part.edits.filter((edit) => edit.frame === frame.index).length} edits on frame</span>
                </span>
              </button>
            ))}
          </div>
        </aside>

        <SemanticEditorCanvas
          current={current}
          frame={frame}
          frameIndexes={frameIndexes}
          activePart={activePart}
          activeEditId={activeEditId}
          scaleX={scaleX}
          scaleY={scaleY}
          canvasRef={canvasRef}
          setFrameIndex={setFrameIndex}
          setActiveEditId={setActiveEditId}
          setDragPoint={setDragPoint}
          setShowCopyModal={setShowCopyModal}
          addEdit={addEdit}
          updateEdit={updateEdit}
        />

        <aside className="panel semantic-editor-inspector">
          {activePart ? (
            <>
              <div className="semantic-editor-inspector-head">
                <h3>Selected part</h3>
                <button type="button" className="compact-btn" onClick={() => removePart(activePart.id)}>
                  Delete part
                </button>
              </div>
              <label>
                id
                <input
                  value={activePart.id}
                  onChange={(event) => updatePart(activePart.id, { id: event.currentTarget.value })}
                />
              </label>
              <label>
                label
                <input
                  value={activePart.label}
                  onChange={(event) => updatePart(activePart.id, { label: event.currentTarget.value })}
                />
              </label>
              <label>
                prompt
                <input
                  value={activePart.prompt}
                  onChange={(event) => updatePart(activePart.id, { prompt: event.currentTarget.value })}
                />
              </label>
              <label>
                mobility
                <select
                  value={activePart.mobility}
                  onChange={(event) =>
                    updatePart(activePart.id, { mobility: event.currentTarget.value as SemanticManualPart["mobility"] })
                  }
                >
                  {MOBILITY.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                persistence
                <select
                  value={activePart.persistence}
                  onChange={(event) =>
                    updatePart(activePart.id, {
                      persistence: event.currentTarget.value as SemanticManualPart["persistence"],
                    })
                  }
                >
                  {PERSISTENCE.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <div className="semantic-editor-stabilize">
                <h4>Part stabilize</h4>
                <label className="semantic-editor-toggle-label">
                  <span>
                    enabled{" "}
                    <InfoTip text="Per-part override. Wyłącza repair, patch lock i medianę dla tej części, nawet gdy globalny part-stabilize jest ON." />
                  </span>
                  <input
                    type="checkbox"
                    checked={stabilizeSettings(activePart).enabled}
                    onChange={(event) => updateStabilize(activePart.id, { enabled: event.currentTarget.checked })}
                  />
                </label>
                <label className="semantic-editor-toggle-label">
                  <span>
                    repair{" "}
                    <InfoTip text="Pozwala backendowi odtworzyć missing/rejected maskę tej części z najbliższej dobrej klatki." />
                  </span>
                  <input
                    type="checkbox"
                    checked={stabilizeSettings(activePart).repairEnabled}
                    onChange={(event) => updateStabilize(activePart.id, { repairEnabled: event.currentTarget.checked })}
                  />
                </label>
                <label>
                  <span>
                    repair search{" "}
                    <InfoTip text="Mnożnik promienia template matching dla tej części. Większy pomaga przy szybkim ruchu, ale może złapać zły element." />
                  </span>
                  <input
                    type="number"
                    min="0.1"
                    max="3"
                    step="0.05"
                    value={stabilizeSettings(activePart).repairSearchScale}
                    onChange={(event) =>
                      updateStabilize(activePart.id, { repairSearchScale: Number(event.currentTarget.value) })
                    }
                  />
                </label>
                <label>
                  <span>
                    patch lock{" "}
                    <InfoTip text="Mnożnik siły mieszania reference patch dla static/low/accessory. 0 wyłącza patch lock dla tej części." />
                  </span>
                  <input
                    type="number"
                    min="0"
                    max="1.5"
                    step="0.05"
                    value={stabilizeSettings(activePart).patchLockStrength}
                    onChange={(event) =>
                      updateStabilize(activePart.id, { patchLockStrength: Number(event.currentTarget.value) })
                    }
                  />
                </label>
                <label>
                  <span>
                    median{" "}
                    <InfoTip text="Mnożnik lokalnej mediany temporalnej. 0 wyłącza median blend dla tej części." />
                  </span>
                  <input
                    type="number"
                    min="0"
                    max="1.5"
                    step="0.05"
                    value={stabilizeSettings(activePart).medianStrength}
                    onChange={(event) =>
                      updateStabilize(activePart.id, { medianStrength: Number(event.currentTarget.value) })
                    }
                  />
                </label>
              </div>
              <div className="semantic-editor-edit-list">
                {activeEdits.map((edit) => {
                  const editIndex = activePart.edits.indexOf(edit);
                  const key = editKey(activePart.id, editIndex);
                  const box = edit.type === "bbox" ? editBoxRaw(edit) : null;
                  const label = box
                    ? `${edit.type} [${box.map((value) => Math.round(value)).join(", ")}]`
                    : `${edit.type} ${Math.round(edit.x ?? 0)}, ${Math.round(edit.y ?? 0)}`;
                  return (
                    <div
                      key={key}
                      className={`semantic-editor-edit-row ${activeEditId === key ? "semantic-editor-edit-row-active" : ""}`}
                      onClick={() => setActiveEditId(key)}
                    >
                      <span>{label}</span>
                      <button
                        type="button"
                        className="semantic-editor-edit-remove"
                        title="remove"
                        onClick={(event) => {
                          event.stopPropagation();
                          removeEdit(activePart.id, editIndex);
                        }}
                      >
                        ×
                      </button>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <p className="muted-copy">No part selected</p>
          )}
        </aside>
      </section>

      {showCopyModal && (
        <div className="semantic-editor-modal-overlay" onClick={() => setShowCopyModal(false)}>
          <div className="semantic-editor-modal" onClick={(event) => event.stopPropagation()}>
            <h3>Copy edits to all frames?</h3>
            <p>Czy chcesz przekopiować obecny układ punktów do pozostałych klatek?</p>
            <div className="semantic-editor-modal-actions">
              <button type="button" className="compact-btn" onClick={() => setShowCopyModal(false)}>
                No
              </button>
              <button type="button" className="primary-btn" onClick={copyEditsToAllFrames}>
                Yes
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
