import React from "react";

export function FrameStepper({
  frameIndexes,
  value,
  onChange,
  labelPrefix = "Frame",
}: {
  frameIndexes: number[];
  value: number;
  onChange: (index: number) => void;
  labelPrefix?: string;
}) {
  const currentOffset = frameIndexes.indexOf(value);
  const activeOffset = currentOffset >= 0 ? currentOffset : 0;
  const activeFrame = frameIndexes[activeOffset];
  const hasFrames = frameIndexes.length > 0;

  return (
    <div className="frame-stepper">
      <button
        type="button"
        className="compact-btn frame-stepper-btn"
        onClick={() => activeOffset > 0 && onChange(frameIndexes[activeOffset - 1])}
        disabled={!hasFrames || activeOffset <= 0}
        aria-label="Previous frame"
      >
        {"<"}
      </button>
      <strong className="frame-stepper-label">
        {hasFrames ? `${labelPrefix} ${activeFrame}` : `${labelPrefix} -`}
      </strong>
      <button
        type="button"
        className="compact-btn frame-stepper-btn"
        onClick={() => activeOffset < frameIndexes.length - 1 && onChange(frameIndexes[activeOffset + 1])}
        disabled={!hasFrames || activeOffset >= frameIndexes.length - 1}
        aria-label="Next frame"
      >
        {">"}
      </button>
    </div>
  );
}
