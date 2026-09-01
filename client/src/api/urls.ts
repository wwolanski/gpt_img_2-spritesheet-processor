export function previewUrl(previewId: string, file: string): string {
  return `/api/asset-pipeline/preview/${encodeURIComponent(previewId)}/${file.split("/").map(encodeURIComponent).join("/")}`;
}

export function sourceUrl(sourceName: string): string {
  return `/api/asset-pipeline/source/${encodeURIComponent(sourceName)}`;
}
