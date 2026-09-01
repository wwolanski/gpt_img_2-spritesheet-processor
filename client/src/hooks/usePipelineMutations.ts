import { useMutation } from "@tanstack/react-query";
import { processSource, comparePipelines, compareAllSources, exportPreview } from "../api/pipeline";
import { usePipelineStore } from "../stores/pipelineStore";
import { variantKey, pipelineLabel, controlsForPipeline } from "../utils/controls";
import { cloneControls } from "../utils/pipeline";
import type { PipelineOptions } from "../types/apiContract";

let previewSequence = 0;

export function useProcessMutation() {
  const store = usePipelineStore;

  return useMutation({
    mutationFn: async ({
      source,
      pipelineId,
      options,
      signal,
    }: {
      source: string;
      pipelineId: string;
      options: PipelineOptions;
      signal?: AbortSignal;
    }) => {
      return processSource(source, pipelineId, options, signal);
    },
    onMutate: ({ source, pipelineId }) => {
      const state = store.getState();
      previewSequence++;
      const seq = previewSequence;
      const ctrl = cloneControls({
        ...state.controls,
        source,
        pipelineId,
      });
      state.upsertRunningVariant(pipelineId, source, ctrl);
      state.setStatus(
        pipelineId ? `Przetwarzanie ${pipelineLabel(state.config, pipelineId)}...` : "Przetwarzanie preview...",
      );
      state.setLoading(true);
      return { seq };
    },
    onSuccess: (result, variables, context) => {
      if (context.seq !== previewSequence) return;
      const state = store.getState();
      const label = pipelineLabel(state.config, result.pipelineId);
      state.setCurrent(result, label);
      state.setStatus(`Preview gotowy. Pipeline: ${result.pipelineId}. Score: ${result.metrics.score}`);
      state.setLoading(false);
    },
    onError: (error, variables, context) => {
      if (!context || context.seq !== previewSequence) return;
      const state = store.getState();
      state.markVariantError(variables.pipelineId, variables.source, error);
      state.setStatus(`Błąd renderu: ${error instanceof Error ? error.message : String(error)}`);
      state.setLoading(false);
    },
  });
}

export function useCompareMutation() {
  const store = usePipelineStore;

  return useMutation({
    mutationFn: async ({
      source,
      pipelineIds,
      workers,
      options,
      signal,
    }: {
      source: string;
      pipelineIds: string[];
      workers: number;
      options: PipelineOptions;
      signal?: AbortSignal;
    }) => {
      return comparePipelines(source, pipelineIds, workers, options, signal);
    },
    onMutate: () => {
      const state = store.getState();
      previewSequence++;
      const seq = previewSequence;
      state.setLoading(true);
      state.setStageStatuses("running");
      state.setStatus("Porównanie pipeline...");

      if (!state.config) return { seq, pipelineIds: [], requestedActiveId: null };
      const pipelineIds = state.config.pipelines.filter((p) => p.enabled).map((p) => p.id);
      const requestedActiveId = state.activeVariantId;
      state.setVariants(
        pipelineIds.map((pid) => ({
          id: variantKey(state.controls.source, pid),
          label: pipelineLabel(state.config, pid),
          pipelineId: pid,
          source: state.controls.source,
          controls: controlsForPipeline(state.config, state.controls, pid, state.controls.source, state.pipelineTweaks),
          status: "running" as const,
        })),
      );
      return { seq, pipelineIds, requestedActiveId };
    },
    onSuccess: (response, variables, context) => {
      if (!context || context.seq !== previewSequence) return;
      const state = store.getState();
      const results = response.results.map((result) => ({
        id: variantKey(result.source, result.pipelineId),
        label: pipelineLabel(state.config, result.pipelineId),
        pipelineId: result.pipelineId,
        source: result.source,
        controls: controlsForPipeline(
          state.config,
          state.controls,
          result.pipelineId,
          result.source,
          state.pipelineTweaks,
        ),
        result,
        status: "ready" as const,
      }));
      state.setVariants(results);
      const active = results.find((r) => r.id === context.requestedActiveId) ?? results[0];
      if (active) {
        state.setCurrent(active.result!, active.label, active.controls);
        state.setStatus(
          `Compare gotowy. Aktywny wariant: ${active.label} (${active.result!.metrics.score}). ${response.results.length} pipeline / ${response.workers} workers / ${response.durationMs}ms`,
        );
      }
      state.setLoading(false);
    },
    onError: (error, variables, context) => {
      if (!context || context.seq !== previewSequence) return;
      const state = store.getState();
      state.setVariants(
        state.variants.map((v) => ({
          ...v,
          status: "error" as const,
          error: error instanceof Error ? error.message : String(error),
        })),
      );
      state.setStageStatuses("error");
      state.setStatus(`Błąd compare: ${error instanceof Error ? error.message : String(error)}`);
      state.setLoading(false);
    },
  });
}

export function useCompareMatrixMutation() {
  const store = usePipelineStore;

  return useMutation({
    mutationFn: async ({
      sources,
      pipelineIds,
      workers,
      options,
      signal,
    }: {
      sources: string[];
      pipelineIds: string[];
      workers: number;
      options: PipelineOptions;
      signal?: AbortSignal;
    }) => {
      return compareAllSources(sources, pipelineIds, workers, options, signal);
    },
    onMutate: () => {
      const state = store.getState();
      previewSequence++;
      const seq = previewSequence;
      state.setLoading(true);
      state.setStageStatuses("running");
      state.setStatus("Porównanie wszystkich źródeł...");
      state.setVariants([]);
      return { seq };
    },
    onSuccess: (response, variables, context) => {
      if (context.seq !== previewSequence) return;
      const state = store.getState();
      const results = response.results.map((result) => ({
        id: variantKey(result.source, result.pipelineId),
        label: `${result.source} / ${pipelineLabel(state.config, result.pipelineId)}`,
        pipelineId: result.pipelineId,
        source: result.source,
        controls: controlsForPipeline(
          state.config,
          { ...state.controls, profile: "auto" },
          result.pipelineId,
          result.source,
          state.pipelineTweaks,
          "auto",
        ),
        result,
        status: "ready" as const,
      }));
      state.setVariants(results);
      if (results[0]) {
        state.setCurrent(results[0].result!, results[0].label, results[0].controls);
        state.setStatus(
          `Matrix gotowy: ${response.results.length} tasków / ${response.workers} workers / ${response.durationMs}ms`,
        );
      }
      state.setLoading(false);
    },
    onError: (error, variables, context) => {
      if (!context || context.seq !== previewSequence) return;
      const state = store.getState();
      state.setVariants(
        state.variants.map((v) => ({
          ...v,
          status: "error" as const,
          error: error instanceof Error ? error.message : String(error),
        })),
      );
      state.setStageStatuses("error");
      state.setStatus(`Błąd compare: ${error instanceof Error ? error.message : String(error)}`);
      state.setLoading(false);
    },
  });
}

export function useExportMutation() {
  const store = usePipelineStore;

  return useMutation({
    mutationFn: async ({ previewId, targetName }: { previewId: string; targetName: string }) => {
      return exportPreview(previewId, targetName);
    },
    onMutate: () => {
      store.getState().setExportStatus("Eksport...");
    },
    onSuccess: (response) => {
      store.getState().setExportStatus(`Zapisano do ${response.publicPath}`);
    },
  });
}
