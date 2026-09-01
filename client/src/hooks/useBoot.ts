import { useQuery } from "@tanstack/react-query";
import { fetchDescribe, fetchSources } from "../api/pipeline";
import { usePipelineStore } from "../stores/pipelineStore";
import { useEffect } from "react";

export function useBoot() {
  const initConfig = usePipelineStore((s) => s.initConfig);
  const setSources = usePipelineStore((s) => s.setSources);

  const describe = useQuery({
    queryKey: ["pipeline", "describe"],
    queryFn: fetchDescribe,
    staleTime: Infinity,
  });

  const sources = useQuery({
    queryKey: ["pipeline", "sources"],
    queryFn: fetchSources,
    staleTime: Infinity,
  });

  useEffect(() => {
    if (describe.data && sources.data) {
      const firstSource = sources.data.sources[0]?.name ?? "";
      initConfig(describe.data, firstSource);
      setSources(sources.data.sources);
    }
  }, [describe.data, sources.data, initConfig, setSources]);

  return {
    configLoading: describe.isLoading || sources.isLoading,
    configError: describe.error ?? sources.error,
  };
}
