import React from "react";
import { Rnd } from "react-rnd";
import { FrameStepper } from "../FrameStepper";
import { previewUrl } from "../../api/urls";
import { editKey, clamp, normalizeBox } from "../../utils/edit";
import { editBoxRaw } from "../../utils/semanticEditor";
import type { SemanticDebugFrame, SemanticEdit, SemanticEditorPart } from "../../types/pipeline";

export type DragPoint = { partId: string; editIndex: number };

type SemanticEditorCanvasProps = {
  current: { previewId: string };
  frame: SemanticDebugFrame;
  frameIndexes: number[];
  activePart?: SemanticEditorPart;
  activeEditId: string | null;
  scaleX: number;
  scaleY: number;
  canvasRef: { current: HTMLDivElement | null };
  setFrameIndex: (index: number) => void;
  setActiveEditId: (id: string) => void;
  setDragPoint: React.Dispatch<React.SetStateAction<DragPoint | null>>;
  setShowCopyModal: (show: boolean) => void;
  addEdit: (type: SemanticEdit["type"]) => void;
  updateEdit: (partId: string, editIndex: number, patch: Partial<SemanticEdit>) => void;
};

function PlusIcon() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden>
      <path d="M8 2v12M2 8h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function MinusIcon() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden>
      <path d="M2 8h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function BoxIcon() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="none" aria-hidden>
      <rect x="2" y="2" width="12" height="12" stroke="currentColor" strokeWidth="2" rx="1" />
    </svg>
  );
}

function CopyFramesIcon() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" fill="none" aria-hidden>
      <rect x="3" y="3" width="10" height="10" stroke="currentColor" strokeWidth="2" rx="1" />
      <path d="M6 1h9v9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function SemanticEditorCanvas({
  current,
  frame,
  frameIndexes,
  activePart,
  activeEditId,
  scaleX,
  scaleY,
  canvasRef,
  setFrameIndex,
  setActiveEditId,
  setDragPoint,
  setShowCopyModal,
  addEdit,
  updateEdit,
}: SemanticEditorCanvasProps) {
  return (
    <section className="panel semantic-editor-canvas-panel">
      <div className="semantic-editor-canvas-toolbar">
        <FrameStepper frameIndexes={frameIndexes} value={frame.index} onChange={setFrameIndex} />
        <button
          type="button"
          className="icon-btn icon-btn-green"
          title="Add + point"
          onClick={() => addEdit("positive_point")}
        >
          <PlusIcon />
        </button>
        <button
          type="button"
          className="icon-btn icon-btn-red"
          title="Add - point"
          onClick={() => addEdit("negative_point")}
        >
          <MinusIcon />
        </button>
        <button type="button" className="icon-btn icon-btn-blue" title="Add bbox" onClick={() => addEdit("bbox")}>
          <BoxIcon />
        </button>
        <button
          type="button"
          className="icon-btn icon-btn-yellow"
          title="Copy current edits to all frames"
          onClick={() => setShowCopyModal(true)}
        >
          <CopyFramesIcon />
        </button>
      </div>
      <div className="semantic-editor-canvas-head">
        <strong>{activePart?.label ?? "No part"}</strong>
        <span>
          {frame.width}x{frame.height}
        </span>
      </div>
      <div
        ref={(node) => {
          canvasRef.current = node;
        }}
        className="semantic-editor-canvas"
        style={{ aspectRatio: `${frame.width} / ${frame.height}` }}
      >
        <img
          src={previewUrl(current.previewId, frame.files.samRgb)}
          alt={`sam_rgb_frame ${frame.index}`}
          draggable={false}
        />
        {activePart?.edits.map((edit, editIndex) => {
          if (edit.frame !== frame.index) return null;
          const key = editKey(activePart.id, editIndex);
          if (edit.type === "bbox") {
            const box = editBoxRaw(edit);
            if (!box) return null;
            const [x0, y0, x1, y1] = normalizeBox(box, frame.width, frame.height);
            return (
              <Rnd
                key={key}
                bounds="parent"
                size={{ width: (x1 - x0) * scaleX, height: (y1 - y0) * scaleY }}
                position={{ x: x0 * scaleX, y: y0 * scaleY }}
                minWidth={8}
                minHeight={8}
                className={`semantic-editor-box ${activeEditId === key ? "semantic-editor-box-active" : ""}`}
                onMouseDown={() => setActiveEditId(key)}
                onDragStart={() => setActiveEditId(key)}
                onResizeStart={() => setActiveEditId(key)}
                onDragStop={(_, data) => {
                  const width = x1 - x0;
                  const height = y1 - y0;
                  const nx0 = data.x / scaleX;
                  const ny0 = data.y / scaleY;
                  updateEdit(activePart.id, editIndex, {
                    box: normalizeBox([nx0, ny0, nx0 + width, ny0 + height], frame.width, frame.height),
                  });
                }}
                onResizeStop={(_, __, ref, ___, position) => {
                  const nx0 = position.x / scaleX;
                  const ny0 = position.y / scaleY;
                  const nx1 = nx0 + ref.offsetWidth / scaleX;
                  const ny1 = ny0 + ref.offsetHeight / scaleY;
                  updateEdit(activePart.id, editIndex, {
                    box: normalizeBox([nx0, ny0, nx1, ny1], frame.width, frame.height),
                  });
                }}
              >
                <span>{activePart.label}</span>
              </Rnd>
            );
          }
          const x = clamp(edit.x ?? 0, 0, frame.width - 1);
          const y = clamp(edit.y ?? 0, 0, frame.height - 1);
          return (
            <button
              key={key}
              type="button"
              className={`semantic-editor-point ${edit.type === "negative_point" ? "semantic-editor-point-negative" : ""} ${activeEditId === key ? "semantic-editor-point-active" : ""}`}
              style={{ left: `${(x / frame.width) * 100}%`, top: `${(y / frame.height) * 100}%` }}
              onPointerDown={(event) => {
                event.currentTarget.setPointerCapture(event.pointerId);
                setActiveEditId(key);
                setDragPoint({ partId: activePart.id, editIndex });
              }}
              title={`${edit.type} ${Math.round(x)}, ${Math.round(y)}`}
            />
          );
        })}
      </div>
    </section>
  );
}
