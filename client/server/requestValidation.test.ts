import { describe, expect, it } from "vitest";
import {
  HttpError,
  requireSourceName,
  requireSourceNames,
  requireWorkers,
  validatePipelineIds,
} from "./requestValidation";
import { apiErrorPayload } from "./errorContract";

function expectHttpError(action: () => unknown, statusCode: number, code: string): void {
  try {
    action();
    throw new Error("Expected HttpError");
  } catch (error) {
    expect(error).toBeInstanceOf(HttpError);
    expect(error).toMatchObject({ statusCode, code });
  }
}

describe("local API request validation", () => {
  it("accepts safe image names and rejects paths", () => {
    expect(requireSourceName("pirate_outline.png")).toBe("pirate_outline.png");
    expectHttpError(() => requireSourceName("../secret.png"), 422, "invalid_source");
    expectHttpError(() => requireSourceName("notes.txt"), 422, "invalid_source");
  });

  it("enforces uniqueness and worker bounds", () => {
    expect(requireSourceNames(["a.png", "b.webp"])).toEqual(["a.png", "b.webp"]);
    expectHttpError(() => requireSourceNames(["a.png", "a.png"]), 422, "invalid_sources");
    expect(requireWorkers(4)).toBe(4);
    expectHttpError(() => requireWorkers(0), 422, "invalid_workers");
  });

  it("rejects duplicate pipeline ids", () => {
    validatePipelineIds(["outline-ink", "distance-classic"]);
    expectHttpError(() => validatePipelineIds(["outline-ink", "outline-ink"]), 422, "invalid_pipelines");
  });

  it("serializes API errors into one stable envelope", () => {
    expect(apiErrorPayload(new HttpError(422, "Invalid source.", "invalid_source"))).toEqual({
      ok: false,
      error: { code: "invalid_source", message: "Invalid source." },
    });
    expect(apiErrorPayload(new Error("unexpected"))).toEqual({
      ok: false,
      error: { code: "internal_error", message: "Internal asset pipeline error." },
    });
  });
});
