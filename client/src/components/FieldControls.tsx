import React from "react";
import type { ControlsState } from "../types/pipeline";
import { usePipelineStore } from "../stores/pipelineStore";

/* ─── Range ─── */
export function RangeField({
  field,
  label,
  min,
  max,
  step,
}: {
  field: keyof ControlsState;
  label: string;
  min: number;
  max: number;
  step: number;
}) {
  const value = String(usePipelineStore((s) => s.controls[field]));
  const setControl = usePipelineStore((s) => s.setControl);

  return React.createElement(
    "label",
    { className: "field" },
    React.createElement("span", null, label, " ", React.createElement("strong", null, value)),
    React.createElement("input", {
      "data-field": field,
      type: "range",
      min,
      max,
      step,
      value,
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => setControl(field, Number(e.target.value)),
      onInput: (e: React.ChangeEvent<HTMLInputElement>) => setControl(field, Number(e.target.value)),
    }),
    React.createElement("input", {
      "data-field": field,
      className: "field-number",
      type: "number",
      min,
      max,
      step,
      value,
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => setControl(field, Number(e.target.value)),
      onInput: (e: React.ChangeEvent<HTMLInputElement>) => setControl(field, Number(e.target.value)),
    }),
  );
}

/* ─── Select ─── */
export type SelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

export function SelectField({
  field,
  label,
  options,
}: {
  field: keyof ControlsState;
  label: string;
  options: SelectOption[];
}) {
  const value = String(usePipelineStore((s) => s.controls[field]));
  const setControl = usePipelineStore((s) => s.setControl);

  return React.createElement(
    "label",
    { className: "field" },
    React.createElement("span", null, label),
    React.createElement(
      "select",
      {
        "data-field": field,
        value,
        onChange: (e: React.ChangeEvent<HTMLSelectElement>) => setControl(field, e.target.value),
      },
      options.map((option) =>
        React.createElement(
          "option",
          {
            key: option.value,
            value: option.value,
            disabled: option.disabled,
          },
          option.label,
        ),
      ),
    ),
  );
}

/* ─── Toggle ─── */
export function ToggleField({ field, label }: { field: keyof ControlsState; label: string }) {
  const value = Boolean(usePipelineStore((s) => s.controls[field]));
  const setControl = usePipelineStore((s) => s.setControl);

  return React.createElement(
    "label",
    { className: "switch-field" },
    React.createElement("span", null, label),
    React.createElement("input", {
      type: "checkbox",
      checked: value,
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => setControl(field, e.target.checked),
    }),
    React.createElement("strong", null, value ? "ON" : "OFF"),
  );
}

/* ─── Text ─── */
export function TextField({ field, label, value }: { field: keyof ControlsState; label: string; value: string }) {
  const setControl = usePipelineStore((s) => s.setControl);

  return React.createElement(
    "label",
    { className: "field" },
    React.createElement("span", null, label),
    React.createElement("input", {
      "data-field": field,
      type: "text",
      value,
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => setControl(field, e.target.value),
    }),
  );
}

/* ─── Spinner ─── */
export function Spinner({ active }: { active: boolean }) {
  return active
    ? React.createElement("span", { className: "spinner", "aria-label": "running" })
    : React.createElement("span", { className: "status-spacer" });
}

/* ─── Status icon ─── */
export function StatusIcon({ status, included }: { status: string; included: boolean }) {
  if (status === "running") return React.createElement(Spinner, { active: true });
  if (status === "error") return React.createElement("span", { className: "status-dot status-error" });
  return React.createElement("span", {
    className: `status-dot ${included ? "status-enabled" : "status-disabled"}`,
  });
}

/* ─── Stage toggle ─── */
export function StageToggle({
  group,
}: {
  group: { id: string; included: boolean; configurable: boolean; description: string };
}) {
  const setControl = usePipelineStore((s) => s.setControl);
  const pipelineStages = usePipelineStore((s) => s.controls.pipelineStages);

  const toggle = (e: React.ChangeEvent<HTMLInputElement>) => {
    setControl("pipelineStages", {
      ...pipelineStages,
      [group.id]: e.target.checked,
    });
  };

  return React.createElement(
    React.Fragment,
    null,
    React.createElement(
      "label",
      { className: "switch-field" },
      React.createElement("span", null, "Stage"),
      React.createElement("input", {
        type: "checkbox",
        checked: group.included,
        disabled: !group.configurable,
        onChange: toggle,
      }),
      React.createElement("strong", null, group.included ? "ON" : "OFF"),
    ),
    group.description ? React.createElement("p", { className: "field-help" }, group.description) : null,
  );
}
