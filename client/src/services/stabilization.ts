export function flowBlendRatio(result: { stabilization?: Record<string, unknown> }): string | null {
  const flow = result.stabilization?.flowDeflicker;
  if (
    typeof flow === "object" &&
    flow !== null &&
    !Array.isArray(flow) &&
    typeof (flow as Record<string, unknown>).blendedPixelRatio === "number"
  ) {
    return String((flow as Record<string, unknown>).blendedPixelRatio);
  }
  return null;
}

export function stabilizationRows(result: { stabilization?: Record<string, unknown> }): {
  flowRatio: string | null;
  stableRatio: string | null;
} {
  const flowRatio = flowBlendRatio(result);
  const temporal = result.stabilization?.temporalDeflicker;
  const stableRatio =
    typeof temporal === "object" &&
    temporal !== null &&
    !Array.isArray(temporal) &&
    typeof (temporal as Record<string, unknown>).stablePixelRatio === "number"
      ? String((temporal as Record<string, unknown>).stablePixelRatio)
      : null;
  return { flowRatio, stableRatio };
}
