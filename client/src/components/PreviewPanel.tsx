import { usePipelineStore } from "../stores/pipelineStore";
import { WorkbenchBar } from "./WorkbenchBar";
import { AnimationCard } from "./AnimationCard";
import { SourceCard } from "./SourceCard";
import { ProcessedCanvas } from "./ProcessedCanvas";
import { PartInspector } from "./PartInspector";
import type { PipelineAction } from "../types/actions";

function PreviewMetaBar() {
  const current = usePipelineStore((s) => s.current);

  return (
    <div className="preview-meta-bar">
      <span>
        Profile <strong>{current?.profile ?? "-"}</strong>
      </span>
      <span>
        Pipeline <strong>{current?.pipelineId ?? "-"}</strong>
      </span>
      <span>
        Frames <strong>{current?.frames.length ?? 0}</strong>
      </span>
      <span>
        Score <strong>{current?.metrics.score ?? "-"}</strong>
      </span>
    </div>
  );
}

export function PreviewPanel({ onAction }: { onAction: (action: PipelineAction) => void }) {
  return (
    <main className="preview-panel">
      <WorkbenchBar onAction={onAction} />
      <div className="panel preview-stack">
        <AnimationCard />
        <PreviewMetaBar />
        <div className="preview-columns">
          <SourceCard />
          <ProcessedCanvas />
          <PartInspector />
        </div>
      </div>
    </main>
  );
}
