import React from "react";
import { usePipelineStore } from "../stores/pipelineStore";
import type {
  SemanticDebugPartSpec,
  SemanticDebugTrack,
  SemanticInputMode,
  SemanticManualPart,
  SemanticPart,
} from "../types/pipeline";
import { INPUT_MODE_HINTS } from "../constants/semantic";
import { InfoTip } from "./semantic/InfoTip";
import { DebugFramePanel } from "./semantic/DebugFramePanel";
import { DebugPartControls } from "./semantic/DebugPartControls";
import { DebugIssuesPanel } from "./semantic/DebugIssuesPanel";
import type { PipelineAction } from "../types/actions";

function partFromCurrent(part: SemanticPart): SemanticManualPart {
  return {
    id: part.id,
    label: part.label,
    prompt: part.label,
    mobility: part.mobility,
    persistence: part.persistence,
  };
}

export function SemanticDebugWorkspace({ onAction }: { onAction: (action: PipelineAction) => void }) {
  const current = usePipelineStore((s) => s.current);
  const controls = usePipelineStore((s) => s.controls);
  const activePartId = usePipelineStore((s) => s.activePartId);
  const setActivePartId = usePipelineStore((s) => s.setActivePartId);
  const setSemanticManualParts = usePipelineStore((s) => s.setSemanticManualParts);
  const clearSemanticEdits = usePipelineStore((s) => s.clearSemanticEdits);
  const [frameIndex, setFrameIndex] = React.useState(0);
  const [issueFilter, setIssueFilter] = React.useState("all");
  const [overlayLayers, setOverlayLayers] = React.useState({
    qwen: true,
    sam: true,
    track: true,
    mask: true,
  });

  const semantic = current?.semantic;
  const debug = current?.semanticDebug;
  const frameIndexes = debug?.frames.map((frame) => frame.index) ?? [];
  const qwenSpecs = (debug?.qwenGrounding ?? debug?.partSpecs ?? []) as SemanticDebugPartSpec[];
  const parts =
    (semantic?.parts?.length ?? 0) > 0
      ? semantic!.parts
      : qwenSpecs.map((part, index) => ({
          id: part.id,
          label: part.label,
          color: ["#FFB000", "#74FFD8", "#FF8D8D", "#B8D7FF", "#D8FF6A", "#D2AAFF"][index % 6],
          mobility: part.mobility,
          persistence: part.persistence,
          confidence: Math.max(0, ...(part.grounding ?? []).map((hint) => hint.confidence)),
          presence: (debug?.frames ?? []).map((frame) =>
            (part.grounding ?? []).some((hint) => hint.frame === frame.index),
          ),
          warnings: [],
          maskStatuses: undefined,
          frameMetrics: undefined,
          trackSummary: undefined,
          masks: undefined,
          boxes: (debug?.frames ?? []).map(() => null),
        }));
  const issues = semantic?.semanticIssues ?? [];
  const activePart = parts.find((part) => part.id === activePartId) ?? parts[0];
  const manualPart =
    controls.semanticManualParts.find((part) => part.id === activePart?.id) ??
    (activePart ? partFromCurrent(activePart) : undefined);
  const debugFrame = debug?.frames.find((frame) => frame.index === frameIndex) ?? debug?.frames[0];
  const activeSpec = qwenSpecs.find((part) => part.id === activePart?.id);
  const rawTrack = (debug?.sam3RawParts ?? []).find((part: SemanticDebugTrack) => part.id === activePart?.id);
  const validatedTrack = (debug?.sam3ValidatedParts ?? parts).find((part) => part.id === activePart?.id);
  const activeQwenGrounding = activeSpec?.grounding?.filter((hint) => hint.frame === frameIndex) ?? [];
  const activeGroundingEdits = (debug?.groundingEdits ?? []).filter(
    (edit) => edit.partId === activePart?.id && edit.frame === frameIndex,
  );
  const activeManualEdits = (debug?.manualEdits ?? []).filter(
    (edit) => edit.partId === activePart?.id && edit.frame === frameIndex,
  );
  const activeSam3Edits = (debug?.sam3Edits ?? []).filter(
    (edit) => edit.partId === activePart?.id && edit.frame === frameIndex,
  );
  const activeRawMask = rawTrack?.masks?.[frameIndex];
  const activeValidatedMask = validatedTrack?.masks?.[frameIndex];
  const activeTrackBox = validatedTrack?.boxes?.[frameIndex];
  const activeMaskStatus = validatedTrack?.maskStatuses?.[frameIndex] ?? activePart?.maskStatuses?.[frameIndex];
  const activeFrameMetric = validatedTrack?.frameMetrics?.[frameIndex] ?? activePart?.frameMetrics?.[frameIndex];
  const postprocessLabel = debug?.audit?.partStabilize
    ? "stabilized"
    : debug?.audit?.partMaskValidate
      ? "validated"
      : "raw SAM3";
  const qwenCache = (debug?.audit?.qwenCache ?? {}) as {
    enabled?: boolean;
    status?: string;
    hit?: boolean;
    id?: string | null;
    path?: string | null;
  };
  const qwenCacheLabel = qwenCache.status ? `${qwenCache.status}${qwenCache.id ? ` ${qwenCache.id}` : ""}` : "unknown";
  const resolution = debug?.resolutionContract;
  const editCounts = (debug?.audit?.sam3EditCounts ?? {}) as {
    grounding?: number;
    manual?: number;
    total?: number;
  };
  const firstFrame = debug?.frames[0];
  const semanticSize = firstFrame ? `${firstFrame.width}x${firstFrame.height}` : "-";
  const outputScale = resolution?.outputScale ?? (debug?.audit?.outputScale as { x?: number; y?: number } | undefined);
  const scaleLabel = outputScale ? `${outputScale.x ?? 1}x${outputScale.y ?? 1}` : "1x1";

  React.useEffect(() => {
    if (frameIndexes.length === 0) return;
    if (!frameIndexes.includes(frameIndex)) {
      setFrameIndex(frameIndexes[0]);
    }
  }, [frameIndexes, frameIndex]);

  const upsertManualPart = (patch: Partial<SemanticManualPart>) => {
    if (!manualPart) return;
    const nextPart = { ...manualPart, ...patch };
    const exists = controls.semanticManualParts.some((part) => part.id === nextPart.id);
    const next = exists
      ? controls.semanticManualParts.map((part) => (part.id === nextPart.id ? nextPart : part))
      : [...controls.semanticManualParts, nextPart];
    setSemanticManualParts(next);
  };

  const removeManualPart = () => {
    if (!manualPart) return;
    setSemanticManualParts(controls.semanticManualParts.filter((part) => part.id !== manualPart.id));
  };

  const useDetectedParts = () => {
    setSemanticManualParts(parts.map(partFromCurrent));
  };

  const toggleOverlayLayer = (key: keyof typeof overlayLayers) => {
    setOverlayLayers((current) => ({ ...current, [key]: !current[key] }));
  };

  return React.createElement(
    "main",
    { className: "semantic-debug-page" },
    React.createElement(
      "div",
      { className: "panel semantic-debug-toolbar" },
      React.createElement(
        "div",
        { className: "semantic-debug-title" },
        React.createElement("h2", null, "Semantic/SAM3 Debug"),
        React.createElement("p", null, current ? `${current.source} / ${current.pipelineId}` : "Brak aktywnego runu"),
        React.createElement(
          "p",
          { className: "semantic-debug-purpose" },
          "Cel: zobaczyć dokładnie, co backend przygotował dla Qwen3/SAM3, gdzie powstaje maska i które problemy wymagają ręcznej korekty.",
        ),
      ),
      React.createElement(
        "div",
        { className: "semantic-mode-readout" },
        React.createElement("span", null, "Qwen3/SAM3 input"),
        React.createElement("strong", null, debug?.inputMode ?? controls.semanticInputMode),
        React.createElement("span", null, `semantic ${semanticSize}`),
        React.createElement("span", null, `output scale ${scaleLabel}`),
        React.createElement(
          "span",
          null,
          `SAM3 edits ${editCounts.total ?? 0} (${editCounts.grounding ?? 0} grounding / ${editCounts.manual ?? 0} manual)`,
        ),
        React.createElement(
          "span",
          { className: `qwen-cache-pill qwen-cache-${qwenCache.status ?? "unknown"}` },
          `cache ${qwenCacheLabel}`,
        ),
        React.createElement(InfoTip, {
          text: `${INPUT_MODE_HINTS[(debug?.inputMode ?? controls.semanticInputMode) as SemanticInputMode]} Qwen/SAM3 dostają semantic-space przed upscale. ${resolution?.note ?? ""} Qwen cache: ${qwenCacheLabel}${qwenCache.path ? ` (${qwenCache.path})` : ""}.`,
        }),
      ),
      React.createElement(
        "button",
        { type: "button", className: "primary-btn", onClick: () => onAction("process") },
        "Rerun",
      ),
    ),
    React.createElement(
      "section",
      { className: "semantic-debug-grid" },
      React.createElement(DebugFramePanel, {
        debugFrame,
        current,
        frameIndexes,
        frameIndex,
        setFrameIndex,
        overlayLayers,
        toggleOverlayLayer,
        activeQwenGrounding,
        activeGroundingEdits,
        activeSam3Edits,
        activeRawMask,
        activeValidatedMask,
        activeTrackBox: activeTrackBox
          ? { x: activeTrackBox.x, y: activeTrackBox.y, width: activeTrackBox.width, height: activeTrackBox.height }
          : null,
        activeMaskStatus,
        activeFrameMetric,
        postprocessLabel,
      }),
      React.createElement(DebugPartControls, {
        parts,
        activePart,
        setActivePartId,
        manualPart,
        upsertManualPart,
        removeManualPart,
        useDetectedParts,
        clearSemanticEdits,
        activeQwenGrounding,
        activeGroundingEdits,
        activeManualEdits,
        rawTrack,
        validatedTrack,
        frameIndex,
        controls,
      }),
      React.createElement(DebugIssuesPanel, {
        issues,
        issueFilter,
        setIssueFilter,
        setActivePartId,
        setFrameIndex,
        audit: debug?.audit ?? {},
      }),
    ),
  );
}
