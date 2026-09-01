import React from "react";
import { usePipelineStore } from "../stores/pipelineStore";
import { stageGroups } from "../utils/stage";
import { RangeField, SelectField, StageToggle, ToggleField } from "./FieldControls";
import type { ControlsState, DescribeResponse } from "../types/pipeline";
import { RANGE_CONFIG } from "../constants/controls";
import { InfoTip } from "./semantic/InfoTip";

export function StageControls() {
  const config = usePipelineStore((s) => s.config);
  const controls = usePipelineStore((s) => s.controls);
  const activeStageId = usePipelineStore((s) => s.activeStageId);

  const groups = stageGroups(config, controls);
  const activeGroup = groups.find((g) => g.id === activeStageId);

  if (!activeGroup) {
    return React.createElement("p", { className: "field-help" }, "No settings for this stage");
  }

  return React.createElement(
    "div",
    { className: "control-group" },
    React.createElement("h3", { className: "control-group-label" }, activeGroup.label),
    React.createElement(StageToggle, { group: activeGroup }),
    activeGroup.fields.length > 0
      ? activeGroup.fields.map((field) => fieldControl(field, config))
      : React.createElement("p", { className: "field-help" }, "No settings for this stage"),
  );
}

function fieldControl(field: keyof ControlsState, config: DescribeResponse | undefined): React.ReactNode {
  const tip = FIELD_TIPS[field];
  const range = RANGE_CONFIG[field];
  if (range) {
    return withTip(
      field,
      React.createElement(RangeField, {
        field,
        label: range[0],
        min: range[1],
        max: range[2],
        step: range[3],
      }),
      tip,
    );
  }

  if (field === "neutralizeEdges") {
    return React.createElement(SelectField, {
      key: field,
      field,
      label: "Edge neutralize",
      options: ["auto", "gray", "black", "none"].map((value) => ({
        value,
        label: value,
      })),
    });
  }

  if (field === "despillAlphaMode") {
    return React.createElement(SelectField, {
      key: field,
      field,
      label: "Spill alpha",
      options: [
        { value: "preserve", label: "preserve" },
        { value: "spill-transparent", label: "spill-transparent" },
      ],
    });
  }

  if (field === "upscaleMode") {
    const options = ["none", "nearest-2x", "nearest-4x", config?.capabilities?.auraSr ? "aura-sr" : ""]
      .filter(Boolean)
      .map((value) => ({
        value,
        label: value,
      }));
    return React.createElement(SelectField, {
      key: field,
      field,
      label: "Upscale service",
      options,
    });
  }

  if (field === "semanticInputMode") {
    return React.createElement(
      React.Fragment,
      { key: field },
      React.createElement(SelectField, {
        field,
        label: "Qwen3/SAM3 input",
        options: [
          { value: "neutral_matte", label: "neutral matte" },
          { value: "raw_greenscreen", label: "raw greenscreen" },
          { value: "final_processed", label: "final processed" },
        ],
      }),
      React.createElement(
        "p",
        { className: "field-help" },
        "Wybiera RGB frame wysyłany do Qwen3 i SAM3. Debug page tylko pokazuje wynik tego wyboru.",
      ),
    );
  }

  if (field === "semanticEditorParts") {
    return React.createElement(
      React.Fragment,
      { key: field },
      React.createElement(
        "button",
        {
          type: "button",
          className: "primary-btn semantic-editor-link",
          onClick: () => {
            window.location.hash = "/semantic-editor";
          },
        },
        "Go to editor",
      ),
      React.createElement(
        "p",
        { className: "field-help" },
        "Manualne korekty Qwen/SAM3 hints są w osobnej zakładce, żeby settings nie mieszały się z edycją boxów i punktów.",
      ),
    );
  }

  if (field === "semanticGroundingAllowFrameReassign") {
    return React.createElement(ToggleField, { key: field, field, label: "Allow frame reassignment" });
  }

  if (field === "partStabilizeEnabled") {
    return withTip(field, React.createElement(ToggleField, { field, label: "Enable stabilizer" }), tip);
  }

  if (field === "partRepairEnabled") {
    return withTip(field, React.createElement(ToggleField, { field, label: "Repair missing/rejected" }), tip);
  }

  if (field === "semanticGroundingEmitBbox") {
    return React.createElement(ToggleField, { key: field, field, label: "Emit bbox edits" });
  }

  if (field === "semanticGroundingEmitPositivePoint") {
    return React.createElement(ToggleField, { key: field, field, label: "Emit positive point edits" });
  }

  if (field === "semanticGroundingProjectionMode") {
    return React.createElement(
      React.Fragment,
      { key: field },
      React.createElement(SelectField, {
        field,
        label: "Projection mode",
        options: [
          { value: "by_persistence", label: "by part persistence" },
          { value: "source_only", label: "source frame only" },
          { value: "all_frames", label: "all frames" },
        ],
      }),
      React.createElement(
        "p",
        { className: "field-help" },
        "Steruje tym, czy hint z Qwen zostaje tylko na wybranej klatce, czy jest projektowany na więcej klatek przed SAM3.",
      ),
    );
  }

  if (field === "semanticMaskModel") {
    const models = config?.capabilities?.semanticMaskModels?.length
      ? config.capabilities.semanticMaskModels
      : ["sam3", "yolo26", "vitmatte", "inspirinet"];
    const labels: Record<string, string> = {
      sam3: "SAM3",
      yolo26: "YOLO26 seg",
      vitmatte: "ViTMatte",
      inspirinet: "InSPyReNet",
    };
    return React.createElement(
      React.Fragment,
      { key: field },
      React.createElement(SelectField, {
        field,
        label: "Mask model",
        options: models.map((value) => ({
          value,
          label: labels[value] ?? value,
        })),
      }),
      React.createElement(
        "p",
        { className: "field-help" },
        "Wybiera model używany przez semantic service do maskowania części. YOLO26 wymaga modelu segmentacyjnego; ViTMatte/InSPyReNet są ścieżkami degraded do czasu podpięcia runtime.",
      ),
    );
  }

  return null;
}

function withTip(key: string, node: React.ReactNode, text?: string): React.ReactNode {
  return React.createElement(
    "div",
    { key, className: "field-with-tip" },
    node,
    text ? React.createElement(InfoTip, { text }) : null,
  );
}

const FIELD_TIPS: Partial<Record<keyof ControlsState, string>> = {
  partStabilizeEnabled:
    "Globalny kill-switch dla lokalnej stabilizacji części. Stage może być ON, ale ten toggle pozwala wyłączyć sam algorytm bez zmiany pipeline.",
  partRepairEnabled:
    "Naprawia missing/rejected maski przez przeniesienie najbliższej dobrej maski i template matching. Wyłącz, jeśli repair tworzy złe części.",
  partRepairSearchScale:
    "Mnożnik promienia szukania dla template matching. Wyżej łapie większy ruch, ale zwiększa ryzyko przeskoku na podobny element.",
  partPatchLockStrength:
    "Mnożnik siły reference patch lock dla static/low/accessory. Wyżej stabilniej, ale może wyglądać jak naklejka.",
  partMedianStrength:
    "Mnożnik lokalnej mediany temporalnej. Wyżej mniej migotania kształtu/teksturowania, ale większe ryzyko rozmycia ruchu.",
};
