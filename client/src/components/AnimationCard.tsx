import React from "react";
import { usePipelineStore } from "../stores/pipelineStore";
import { AnimationCanvas } from "./AnimationCanvas";
import { FrameStrip } from "./FrameStrip";
import { BG_SWATCHES } from "../constants/animation";

function PlayIcon() {
  return React.createElement(
    "svg",
    { viewBox: "0 0 24 24", width: 18, height: 18, fill: "currentColor" },
    React.createElement("path", { d: "M8 5v14l11-7z" }),
  );
}

function PauseIcon() {
  return React.createElement(
    "svg",
    { viewBox: "0 0 24 24", width: 18, height: 18, fill: "currentColor" },
    React.createElement("rect", { x: "6", y: "4", width: "4", height: "16" }),
    React.createElement("rect", { x: "14", y: "4", width: "4", height: "16" }),
  );
}

function GamepadIcon() {
  return React.createElement(
    "svg",
    { viewBox: "0 0 24 24", width: 18, height: 18, fill: "currentColor" },
    React.createElement("path", {
      d: "M21 6H3c-1.1 0-2 .9-2 2v8c0 1.1.9 2 2 2h18c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-10 7H8v3H6v-3H3v-2h3V8h2v3h3v2zm4.5 2c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm4-3c-.83 0-1.5-.67-1.5-1.5S18.67 9 19.5 9s1.5.67 1.5 1.5-.67 1.5-1.5 1.5z",
    }),
  );
}

function ShoeIcon() {
  return React.createElement(
    "svg",
    { viewBox: "0 0 24 24", width: 18, height: 18, fill: "currentColor" },
    React.createElement("path", {
      d: "M18 14.5c-1.3 0-2.5-.2-3.6-.6-1.2-.4-2.3-1-3.2-1.8l-4.4-3.7c-.4-.3-.8-.5-1.3-.5H3c-.6 0-1 .4-1 1v5c0 1.1.9 2 2 2h14c1.7 0 3-1.3 3-3v-1c0-.8-.7-1.5-1.5-1.5h-1.5c-.3 0-.5.2-.5.5v.5c0 .3-.2.5-.5.5h-1c-.3 0-.5-.2-.5-.5v-.5c0-.3-.2-.5-.5-.5z",
    }),
  );
}

export function AnimationCard() {
  const current = usePipelineStore((s) => s.current);
  const animBg = usePipelineStore((s) => s.animBg);
  const setAnimBg = usePipelineStore((s) => s.setAnimBg);
  const animPlaying = usePipelineStore((s) => s.animPlaying);
  const setAnimPlaying = usePipelineStore((s) => s.setAnimPlaying);
  const animFps = usePipelineStore((s) => s.animFps);
  const setAnimFps = usePipelineStore((s) => s.setAnimFps);
  const moveSpeed = usePipelineStore((s) => s.moveSpeed);
  const setMoveSpeed = usePipelineStore((s) => s.setMoveSpeed);
  const gamepadActive = usePipelineStore((s) => s.gamepadActive);
  const setGamepadActive = usePipelineStore((s) => s.setGamepadActive);

  return React.createElement(
    "div",
    { className: "anim-card" },
    React.createElement(
      "div",
      { className: "anim-header" },
      React.createElement("h3", null, "Animation preview"),
      React.createElement(
        "span",
        null,
        current ? `${current.normalizedFrameSize.width} x ${current.normalizedFrameSize.height}` : "-",
      ),
    ),
    React.createElement(AnimationCanvas, null),
    React.createElement(
      "div",
      { className: "anim-controls" },
      React.createElement(
        "button",
        {
          type: "button",
          className: "anim-play-btn",
          onClick: () => setAnimPlaying(!animPlaying),
        },
        React.createElement(animPlaying ? PauseIcon : PlayIcon, null),
        animPlaying ? "Pause" : "Start",
      ),
      React.createElement(
        "div",
        { className: "speed-control" },
        React.createElement(
          "button",
          {
            type: "button",
            className: "speed-btn",
            onClick: () => setAnimFps(Math.max(1, animFps - 1)),
          },
          "-",
        ),
        React.createElement("span", { className: "speed-value" }, `${animFps} FPS`),
        React.createElement(
          "button",
          {
            type: "button",
            className: "speed-btn",
            onClick: () => setAnimFps(Math.min(60, animFps + 1)),
          },
          "+",
        ),
      ),
      React.createElement(
        "div",
        { className: "anim-bg-picker" },
        React.createElement("span", { className: "anim-bg-picker-label" }, "Bg"),
        BG_SWATCHES.map((s) =>
          React.createElement("button", {
            key: s.id,
            className: `bg-swatch ${animBg === s.id ? "bg-swatch-active" : ""}`,
            style: { background: s.background },
            onClick: () => setAnimBg(s.id),
          }),
        ),
      ),
      React.createElement(
        "div",
        { className: "speed-control" },
        React.createElement(ShoeIcon, null),
        React.createElement(
          "button",
          {
            type: "button",
            className: "speed-btn",
            onClick: () => setMoveSpeed(Math.max(1, moveSpeed - 1)),
          },
          "-",
        ),
        React.createElement("span", { className: "speed-value" }, moveSpeed),
        React.createElement(
          "button",
          {
            type: "button",
            className: "speed-btn",
            onClick: () => setMoveSpeed(Math.min(30, moveSpeed + 1)),
          },
          "+",
        ),
      ),
      React.createElement(
        "button",
        {
          type: "button",
          className: `gamepad-btn ${gamepadActive ? "gamepad-btn-active" : ""}`,
          onClick: () => setGamepadActive(!gamepadActive),
          title: gamepadActive ? "Disable gamepad controls" : "Enable gamepad controls (A/D)",
        },
        React.createElement(GamepadIcon, null),
      ),
    ),
    React.createElement(FrameStrip, null),
  );
}
