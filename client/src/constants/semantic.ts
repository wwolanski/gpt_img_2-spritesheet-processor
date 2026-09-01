import type { SemanticInputMode, SemanticManualPart } from "../types/pipeline";

export const INPUT_MODES: Array<{ id: SemanticInputMode; label: string; hint: string }> = [
  {
    id: "neutral_matte",
    label: "neutral matte",
    hint: "Domyślny input dla Qwen3 i SAM3: oryginalny RGB obiektu tam, gdzie alpha wykryła foreground; poza obiektem neutralne szare tło.",
  },
  {
    id: "raw_greenscreen",
    label: "raw greenscreen",
    hint: "Testowy input dla Qwen3 i SAM3: surowy RGB crop z zielonym tłem. Uwaga: pipeline nadal używa alpha do crop/frame detection; zmienia się tylko obraz wysyłany do modeli.",
  },
  {
    id: "final_processed",
    label: "final processed",
    hint: "Testowy input dla Qwen3 i SAM3: obraz po docelowym processingu pipeline, z neutralnym tłem poza finalną alphą. Raczej wariant porównawczy.",
  },
];

export const INPUT_MODE_HINTS = Object.fromEntries(INPUT_MODES.map((mode) => [mode.id, mode.hint])) as Record<
  SemanticInputMode,
  string
>;

export const FRAME_VIEWS = [
  {
    key: "rawRgb",
    label: "raw_rgb_frame",
    route: "Debug/source",
    hint: "Surowy RGB crop z oryginalnego spritesheetu. Nie jest wysyłany do Qwen3/SAM3, chyba że Pipeline -> Semantic input = raw greenscreen.",
  },
  {
    key: "baseAlpha",
    label: "base_alpha_frame",
    route: "Backend gate",
    hint: "Maska alpha z etapu detekcji tła. Backend używa jej do neutral matte, crop/frame detection i clippingu masek SAM3. Qwen3/SAM3 nie dostają alpha jako kanału.",
  },
  {
    key: "samRgb",
    label: "sam_rgb_frame",
    route: "Qwen3 + SAM3 input",
    hint: "Dokładny obraz RGB wysyłany do Qwen3 jako frame input i do SAM3 jako obraz segmentowany. Zmieniasz go w Pipeline -> Semantic input.",
  },
  {
    key: "finalRgba",
    label: "final_processed_frame",
    route: "Output/stabilization",
    hint: "Docelowy frame po processingu pipeline. Semantic stabilization modyfikuje ten obraz po maskach SAM3. Nie jest inputem modeli, poza trybem final processed.",
  },
] as const;

export const MOBILITY: SemanticManualPart["mobility"][] = ["static", "low", "medium", "high", "accessory"];
export const PERSISTENCE: SemanticManualPart["persistence"][] = ["always", "occasional"];
