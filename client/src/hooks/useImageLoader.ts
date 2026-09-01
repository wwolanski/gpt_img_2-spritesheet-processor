import { useEffect, useRef } from "react";
import { usePipelineStore } from "../stores/pipelineStore";
import { previewUrl } from "../api/urls";

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Failed to load image: ${src}`));
    img.src = src;
  });
}

export function useImageLoader() {
  const current = usePipelineStore((s) => s.current);
  const setPreviewImages = usePipelineStore((s) => s.setPreviewImages);
  const requestRef = useRef(0);

  useEffect(() => {
    const requestId = requestRef.current + 1;
    requestRef.current = requestId;

    if (!current) {
      setPreviewImages(undefined, undefined);
      return;
    }

    Promise.all([
      loadImage(previewUrl(current.previewId, current.previewFiles.processed)),
      loadImage(previewUrl(current.previewId, current.previewFiles.sheet)),
    ])
      .then(([proc, sheet]) => {
        if (requestRef.current !== requestId) return;
        setPreviewImages(proc, sheet);
      })
      .catch(() => {
        if (requestRef.current !== requestId) return;
        setPreviewImages(undefined, undefined);
      });
  }, [current, setPreviewImages]);
}
