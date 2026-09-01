import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createServer, type ViteDevServer } from "vite";
import { assetPipelinePlugin } from "./assetPipelineApi";

let server: ViteDevServer;

beforeAll(async () => {
  server = await createServer({
    configFile: false,
    root: process.cwd(),
    logLevel: "silent",
    plugins: [assetPipelinePlugin()],
    server: { host: "127.0.0.1", port: 0 },
  });
  await server.listen();
});

afterAll(async () => {
  await server.close();
});

function serverUrl(): string {
  const address = server.httpServer?.address();
  if (!address || typeof address === "string") {
    throw new Error("Test server did not expose a TCP address");
  }
  return `http://127.0.0.1:${address.port}`;
}

describe("asset pipeline local API", () => {
  it("serves the describe contract through the Vite middleware", async () => {
    const response = await fetch(`${serverUrl()}/api/asset-pipeline/describe`);
    const payload = (await response.json()) as { capabilities?: Record<string, unknown>; pipelines?: unknown[] };

    expect(response.status).toBe(200);
    expect(payload.pipelines?.length).toBeGreaterThan(0);
    expect(payload.capabilities).toEqual(
      expect.objectContaining({ auraSr: expect.any(Boolean), sam3: expect.any(Boolean), rife: expect.any(Boolean) }),
    );
  });

  it("returns a stable validation error envelope", async () => {
    const response = await fetch(`${serverUrl()}/api/asset-pipeline/process`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ source: "../secret.png" }),
    });
    const payload = (await response.json()) as { ok?: boolean; error?: { code?: string } };

    expect(response.status).toBe(422);
    expect(payload).toEqual({
      ok: false,
      error: { code: "invalid_source", message: expect.any(String) },
    });
  });
});
