import { useCallback, useRef, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useBoot } from "./hooks/useBoot";
import { useImageLoader } from "./hooks/useImageLoader";
import {
  useProcessMutation,
  useCompareMutation,
  useCompareMatrixMutation,
  useExportMutation,
} from "./hooks/usePipelineMutations";
import { usePipelineStore } from "./stores/pipelineStore";
import { buildOptions, buildPipelineOptions } from "./utils/controls";
import { PipelineShell } from "./components/layout/PipelineShell";
import type { PipelineAction } from "./types/actions";
import "./assetPipeline.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1 } },
});

function AppInner() {
  const { configLoading, configError } = useBoot();
  useImageLoader();

  const stateRef = useRef(usePipelineStore.getState());

  useEffect(() => {
    const unsub = usePipelineStore.subscribe((s) => {
      stateRef.current = s;
    });
    return unsub;
  }, []);

  const autoRunTrigger = usePipelineStore((s) => s.autoRunTrigger);
  const autoRunEnabled = usePipelineStore((s) => s.autoRunEnabled);

  const processMut = useProcessMutation();
  const compareMut = useCompareMutation();
  const compareMatrixMut = useCompareMatrixMutation();
  const exportMut = useExportMutation();

  const mutateRef = useRef(processMut.mutate);
  mutateRef.current = processMut.mutate;

  const autoRunRef = useRef(0);

  useEffect(() => {
    if (autoRunTrigger === 0 || !autoRunEnabled) return;
    window.clearTimeout(autoRunRef.current);
    autoRunRef.current = window.setTimeout(() => {
      const s = usePipelineStore.getState();
      if (!s.controls.source || s.loading) return;
      mutateRef.current({
        source: s.controls.source,
        pipelineId: s.controls.pipelineId,
        options: buildOptions(s.controls),
      });
    }, 320);
    return () => window.clearTimeout(autoRunRef.current);
  }, [autoRunTrigger, autoRunEnabled]);

  const handleAction = useCallback(
    (action: PipelineAction) => {
      const s = stateRef.current;
      if (action !== "export" && s.loading) return;
      if (action !== "export") {
        window.clearTimeout(autoRunRef.current);
      }
      if (action === "process") {
        processMut.mutate({
          source: s.controls.source,
          pipelineId: s.controls.pipelineId,
          options: buildOptions(s.controls),
        });
      } else if (action === "compare") {
        if (!s.config) return;
        const pipelineIds = s.config.pipelines.filter((p) => p.enabled).map((p) => p.id);
        compareMut.mutate({
          source: s.controls.source,
          pipelineIds,
          workers: s.config.capabilities.workers,
          options: {
            ...buildOptions(s.controls),
            pipelineOptions: buildPipelineOptions(s.config, s.controls, pipelineIds, s.pipelineTweaks),
          },
        });
      } else if (action === "compare-all") {
        if (!s.config) return;
        const pipelineIds = s.config.pipelines.filter((p) => p.enabled).map((p) => p.id);
        compareMatrixMut.mutate({
          sources: s.sources.map((src) => src.name),
          pipelineIds,
          workers: s.config.capabilities.workers,
          options: {
            ...buildOptions({ ...s.controls, profile: "auto" }),
            pipelineOptions: buildPipelineOptions(s.config, s.controls, pipelineIds, s.pipelineTweaks, "auto"),
          },
        });
      } else if (action === "export") {
        if (!s.current) return;
        exportMut.mutate({
          previewId: s.current.previewId,
          targetName: s.controls.exportSlug,
        });
      }
    },
    [processMut, compareMut, compareMatrixMut, exportMut],
  );

  if (configLoading) {
    return (
      <div className="pipeline-shell">
        <p style={{ padding: "2rem", color: "#f4fbff" }}>Ładowanie konfiguracji...</p>
      </div>
    );
  }

  if (configError) {
    return (
      <div className="pipeline-shell">
        <p style={{ padding: "2rem", color: "#ff8d8d" }}>Błąd: {String(configError)}</p>
      </div>
    );
  }

  return <PipelineShell onAction={handleAction} />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppInner />
    </QueryClientProvider>
  );
}
