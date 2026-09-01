import { randomUUID } from "node:crypto";
import { existsSync, promises as fs } from "node:fs";
import path, { resolve } from "node:path";
import { spawn } from "node:child_process";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";
import type { JsonObject } from "../src/types/apiContract";
import {
  HttpError,
  MAX_REQUEST_BODY_BYTES,
  decodePathComponent,
  envLimit,
  isInlinePreviewFiles,
  isJsonObject,
  requireObject,
  requireSourceName,
  requireSourceNames,
  requireString,
  requireWorkers,
  validatePipelineId,
  validatePipelineIds,
} from "./requestValidation";
import { logger } from "./logger";
import { apiErrorPayload } from "./errorContract";

const CLIENT_ROOT = resolve(__dirname, "..");
const REPO_ROOT = resolve(CLIENT_ROOT, "..");
const LOCAL_PYTHON_BIN = resolve(REPO_ROOT, ".venv/bin/python");
const PYTHON_BIN = process.env.ASSET_PIPELINE_PYTHON || (existsSync(LOCAL_PYTHON_BIN) ? LOCAL_PYTHON_BIN : "python3");
const PIPELINE_SCRIPT = resolve(REPO_ROOT, "asset_pipeline/pipeline_tool.py");
const SOURCE_ROOT = resolve(REPO_ROOT, "asset_pipeline/sources");
const EXPORT_ROOT = resolve(REPO_ROOT, "asset_pipeline/workbench/exports");
const PUBLIC_GENERATED_ROOT = resolve(REPO_ROOT, "client/public/assets/generated");
const MAX_MEMORY_PREVIEWS = 80;
const MAX_IN_FLIGHT_REQUESTS = envLimit("ASSET_PIPELINE_MAX_IN_FLIGHT_REQUESTS", 2);
const PYTHON_TIMEOUT_MS = envLimit("ASSET_PIPELINE_PYTHON_TIMEOUT_MS", 10 * 60 * 1000);

type MemoryPreview = Map<string, Buffer>;

const memoryPreviews = new Map<string, MemoryPreview>();
let inFlightRequests = 0;

export function assetPipelinePlugin(): Plugin {
  return {
    name: "asset-pipeline-api",
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const requestUrl = req.url;
        if (!requestUrl?.startsWith("/api/asset-pipeline")) {
          next();
          return;
        }

        if (inFlightRequests >= MAX_IN_FLIGHT_REQUESTS) {
          logger.warn("request_rejected", { reason: "busy", method: req.method, url: requestUrl });
          sendApiError(res, new HttpError(429, "Too many pipeline requests in progress.", "busy"));
          return;
        }
        inFlightRequests += 1;

        try {
          const url = new URL(requestUrl, "http://localhost");
          if (req.method === "GET" && url.pathname === "/api/asset-pipeline/describe") {
            await respondWithPython(req, res, ["describe"]);
            return;
          }
          if (req.method === "GET" && url.pathname === "/api/asset-pipeline/sources") {
            await respondWithPython(req, res, ["list-sources"]);
            return;
          }
          if (req.method === "GET" && url.pathname === "/api/asset-pipeline/semantic-presets") {
            await respondWithPython(req, res, ["list-semantic-presets"]);
            return;
          }
          if (req.method === "POST" && url.pathname === "/api/asset-pipeline/semantic-presets") {
            const body = await readJsonBody(req);
            await respondWithPython(
              req,
              res,
              ["save-semantic-preset", "--name", requireString(body.name, "name", 80)],
              requireObject(body.settings, "settings"),
            );
            return;
          }
          if (req.method === "DELETE" && url.pathname.startsWith("/api/asset-pipeline/semantic-presets/")) {
            const presetName = requireString(
              decodePathComponent(url.pathname.slice("/api/asset-pipeline/semantic-presets/".length), "preset name"),
              "name",
              80,
            );
            await respondWithPython(req, res, ["delete-semantic-preset", "--name", presetName]);
            return;
          }
          if (req.method === "POST" && url.pathname === "/api/asset-pipeline/process") {
            const body = await readJsonBody(req);
            const previewId = randomUUID();
            validatePipelineId(body.pipelineId);
            await respondWithPython(
              req,
              res,
              ["process", "--source", requireSourceName(body.source), "--preview-id", previewId],
              body,
            );
            return;
          }
          if (req.method === "POST" && url.pathname === "/api/asset-pipeline/compare") {
            const body = await readJsonBody(req);
            const batchId = randomUUID();
            const workers = requireWorkers(body.workers ?? 10);
            validatePipelineIds(body.pipelineIds);
            await respondWithPython(
              req,
              res,
              [
                "compare",
                "--source",
                requireSourceName(body.source),
                "--batch-id",
                batchId,
                "--workers",
                String(workers),
              ],
              body,
            );
            return;
          }
          if (req.method === "POST" && url.pathname === "/api/asset-pipeline/compare-matrix") {
            const body = await readJsonBody(req);
            const batchId = randomUUID();
            const workers = requireWorkers(body.workers ?? 10);
            const sources = body.sources === undefined ? undefined : requireSourceNames(body.sources);
            validatePipelineIds(body.pipelineIds);
            await respondWithPython(
              req,
              res,
              [
                "compare-matrix",
                ...(sources ?? []).flatMap((source) => ["--source", source]),
                "--batch-id",
                batchId,
                "--workers",
                String(workers),
              ],
              body,
            );
            return;
          }
          if (req.method === "POST" && url.pathname === "/api/asset-pipeline/export") {
            const body = await readJsonBody(req);
            await exportMemoryPreview(
              res,
              requireString(body.previewId, "previewId", 160),
              requireString(body.targetName, "targetName", 120),
              body.overwrite === true,
            );
            return;
          }
          if (req.method === "GET" && url.pathname.startsWith("/api/asset-pipeline/source/")) {
            const sourceName = requireSourceName(
              decodePathComponent(url.pathname.slice("/api/asset-pipeline/source/".length), "source"),
            );
            await serveFile(res, path.join(SOURCE_ROOT, sourceName));
            return;
          }
          if (req.method === "GET" && url.pathname.startsWith("/api/asset-pipeline/preview/")) {
            const relative = decodePathComponent(url.pathname.slice("/api/asset-pipeline/preview/".length), "preview");
            serveMemoryPreview(res, relative);
            return;
          }
          throw new HttpError(404, "Unknown asset pipeline endpoint.", "not_found");
        } catch (error) {
          if (!res.writableEnded) {
            logger.error("request_failed", {
              method: req.method,
              url: requestUrl,
              code: error instanceof HttpError ? error.code : "internal_error",
              message: error instanceof Error ? error.message : String(error),
            });
            sendApiError(res, error);
          }
        } finally {
          inFlightRequests -= 1;
        }
      });
    },
  };
}

async function respondWithPython(
  req: IncomingMessage,
  res: ServerResponse,
  args: string[],
  stdinPayload?: JsonObject,
): Promise<void> {
  const abortController = new AbortController();
  const abort = (): void => {
    if (!res.writableEnded) {
      abortController.abort();
    }
  };
  req.on("aborted", abort);
  try {
    const output = await runPython(args, stdinPayload, abortController.signal);
    if (!abortController.signal.aborted) {
      sendJson(res, 200, output);
    }
  } catch (error) {
    if (!abortController.signal.aborted) {
      throw error;
    }
  } finally {
    req.off("aborted", abort);
  }
}

function runPython(args: string[], stdinPayload?: JsonObject, signal?: AbortSignal): Promise<unknown> {
  return new Promise((resolvePromise, rejectPromise) => {
    let settled = false;
    const finishReject = (error: Error): void => {
      if (settled) return;
      settled = true;
      rejectPromise(error);
    };
    const finishResolve = (value: unknown): void => {
      if (settled) return;
      settled = true;
      resolvePromise(value);
    };
    const child = spawn(PYTHON_BIN, [PIPELINE_SCRIPT, ...args], {
      cwd: REPO_ROOT,
      detached: process.platform !== "win32",
      env: { ...process.env, ASSET_PIPELINE_PREVIEW_STORAGE: "memory" },
    });
    const timeout = setTimeout(() => {
      terminateChild(child);
      finishReject(new HttpError(504, "Pipeline request timed out.", "pipeline_timeout"));
    }, PYTHON_TIMEOUT_MS);
    const abort = (): void => {
      terminateChild(child);
      finishReject(new HttpError(499, "Pipeline request aborted.", "request_aborted"));
    };
    signal?.addEventListener("abort", abort, { once: true });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => finishReject(error));
    child.on("close", (code) => {
      clearTimeout(timeout);
      signal?.removeEventListener("abort", abort);
      if (signal?.aborted) {
        return;
      }
      if (code !== 0) {
        finishReject(pipelineProcessError(stdout, stderr, code));
        return;
      }
      try {
        const output = JSON.parse(stdout) as unknown;
        collectInlinePreviews(output);
        finishResolve(output);
      } catch (error) {
        finishReject(new HttpError(502, `Invalid JSON from pipeline: ${String(error)}`, "pipeline_invalid_response"));
      }
    });

    if (stdinPayload !== undefined) {
      child.stdin.write(JSON.stringify(stdinPayload));
    }
    child.stdin.end();
  });
}

async function readJsonBody(req: IncomingMessage): Promise<JsonObject> {
  const declaredLength = Number(req.headers["content-length"] ?? 0);
  if (Number.isFinite(declaredLength) && declaredLength > MAX_REQUEST_BODY_BYTES) {
    throw new HttpError(413, `Request body exceeds ${MAX_REQUEST_BODY_BYTES} bytes.`, "body_too_large");
  }
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of req) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    size += buffer.length;
    if (size > MAX_REQUEST_BODY_BYTES) {
      throw new HttpError(413, `Request body exceeds ${MAX_REQUEST_BODY_BYTES} bytes.`, "body_too_large");
    }
    chunks.push(buffer);
  }
  if (chunks.length === 0) {
    return {};
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(Buffer.concat(chunks).toString("utf-8"));
  } catch (error) {
    throw new HttpError(400, `Request body must contain valid JSON: ${String(error)}`, "invalid_json");
  }
  if (!isJsonObject(parsed)) {
    throw new HttpError(400, "Request body must be a JSON object.", "invalid_body");
  }
  return parsed;
}

async function serveFile(res: ServerResponse, candidatePath: string): Promise<void> {
  const resolved = path.resolve(candidatePath);
  const allowedRoots = [SOURCE_ROOT];
  if (!allowedRoots.some((root) => isInsideRoot(resolved, root))) {
    sendApiError(res, new HttpError(403, "Forbidden path.", "forbidden_path"));
    return;
  }
  const file = await fs.readFile(resolved);
  res.statusCode = 200;
  res.setHeader("Content-Type", contentTypeFor(resolved));
  res.end(file);
}

function serveMemoryPreview(res: ServerResponse, relativePath: string): void {
  const [previewId, ...fileParts] = relativePath.split("/");
  const filename = fileParts.join("/");
  const preview = memoryPreviews.get(previewId);
  const file = preview?.get(filename);
  if (!file) {
    sendApiError(res, new HttpError(404, "Unknown preview file.", "not_found"));
    return;
  }
  res.statusCode = 200;
  res.setHeader("Content-Type", contentTypeFor(filename));
  res.end(file);
}

async function exportMemoryPreview(
  res: ServerResponse,
  previewId: string,
  targetName: string,
  overwrite: boolean,
): Promise<void> {
  const preview = memoryPreviews.get(previewId);
  if (!preview) {
    sendApiError(res, new HttpError(404, "Unknown preview id.", "not_found"));
    return;
  }
  const safeTarget = targetName.replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-|-$/g, "");
  if (!safeTarget) {
    sendApiError(res, new HttpError(400, "Invalid export target name.", "invalid_export_target"));
    return;
  }

  const exportDir = path.join(EXPORT_ROOT, safeTarget);
  const publicDir = path.join(PUBLIC_GENERATED_ROOT, safeTarget);
  if (!overwrite && (existsSync(exportDir) || existsSync(publicDir))) {
    throw new HttpError(409, "Export target already exists; set overwrite=true to replace it.", "export_exists");
  }
  if (overwrite) {
    await fs.rm(exportDir, { recursive: true, force: true });
    await fs.rm(publicDir, { recursive: true, force: true });
  }
  await fs.mkdir(exportDir, { recursive: true });
  await fs.mkdir(publicDir, { recursive: true });

  const copiedFiles: string[] = [];
  for (const filename of ["processed.png", "alpha.png", "sheet.png", "metadata.json", "source.png"]) {
    const file = preview.get(filename);
    if (!file) {
      continue;
    }
    await fs.writeFile(path.join(exportDir, filename), file);
    await fs.writeFile(path.join(publicDir, filename), file);
    copiedFiles.push(filename);
  }

  const metadataFile = preview.get("metadata.json");
  const metadata = metadataFile ? (JSON.parse(metadataFile.toString("utf-8")) as unknown) : {};
  const exportPayload = {
    target: safeTarget,
    previewId,
    copiedFiles,
    publicPath: `/assets/generated/${safeTarget}`,
    metadata,
  };
  await fs.writeFile(path.join(exportDir, "export.json"), JSON.stringify(exportPayload, null, 2));
  sendJson(res, 200, exportPayload);
}

function collectInlinePreviews(value: unknown): void {
  if (Array.isArray(value)) {
    for (const item of value) {
      collectInlinePreviews(item);
    }
    return;
  }
  if (!isJsonObject(value)) {
    return;
  }

  const previewId = typeof value.previewId === "string" ? value.previewId : "";
  const previewFileData = isInlinePreviewFiles(value.previewFileData) ? value.previewFileData : null;
  if (previewId && previewFileData) {
    delete value.previewFileData;
    const files: MemoryPreview = new Map();
    for (const [filename, base64] of Object.entries(previewFileData)) {
      files.set(filename, Buffer.from(base64, "base64"));
    }
    files.set("metadata.json", Buffer.from(JSON.stringify(value, null, 2), "utf-8"));
    memoryPreviews.set(previewId, files);
    pruneMemoryPreviews();
  }

  for (const item of Object.values(value)) {
    collectInlinePreviews(item);
  }
}

function pruneMemoryPreviews(): void {
  while (memoryPreviews.size > MAX_MEMORY_PREVIEWS) {
    const oldest = memoryPreviews.keys().next().value;
    if (!oldest) {
      return;
    }
    memoryPreviews.delete(oldest);
  }
}

function isInsideRoot(candidatePath: string, root: string): boolean {
  const relative = path.relative(root, candidatePath);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function contentTypeFor(filePath: string): string {
  const extension = path.extname(filePath).toLowerCase();
  if (extension === ".png") return "image/png";
  if (extension === ".jpg" || extension === ".jpeg") return "image/jpeg";
  if (extension === ".webp") return "image/webp";
  if (extension === ".json") return "application/json; charset=utf-8";
  return "application/octet-stream";
}

function sendJson(res: ServerResponse, statusCode: number, payload: unknown): void {
  res.statusCode = statusCode;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(JSON.stringify(payload, null, 2));
}

function sendApiError(res: ServerResponse, error: unknown): void {
  const payload = apiErrorPayload(error);
  if (error instanceof HttpError) {
    sendJson(res, error.statusCode, payload);
    return;
  }
  if (error instanceof Error && (error as Error & { code?: string }).code === "ENOENT") {
    sendJson(res, 404, payload);
    return;
  }
  sendJson(res, 500, payload);
}

function pipelineProcessError(stdout: string, stderr: string, exitCode: number | null): HttpError {
  let message = stderr.trim() || stdout.trim() || `Python exited with code ${exitCode}`;
  let code = "pipeline_error";
  try {
    const payload = JSON.parse(stdout) as unknown;
    if (isJsonObject(payload) && isJsonObject(payload.error)) {
      if (typeof payload.error.message === "string") message = payload.error.message;
      if (typeof payload.error.code === "string") code = payload.error.code;
    } else if (isJsonObject(payload) && typeof payload.error === "string") {
      message = payload.error;
    }
  } catch {
    // Keep the process stderr/stdout as the diagnostic when it is not JSON.
  }
  const statusCode =
    code === "not_found" || /unknown source asset/i.test(message)
      ? 404
      : code === "invalid_config"
        ? 500
        : code === "invalid_request" || /invalid|missing|must be|cannot|exceeds|unsupported|too long/i.test(message)
          ? 422
          : /unknown semantic preset/i.test(message)
            ? 404
            : 500;
  return new HttpError(
    statusCode,
    message,
    code === "pipeline_error" && statusCode < 500 ? "invalid_pipeline_request" : code,
  );
}

function terminateChild(child: ReturnType<typeof spawn>): void {
  if (!child.pid) return;
  try {
    if (process.platform !== "win32") {
      process.kill(-child.pid, "SIGTERM");
    } else {
      child.kill("SIGTERM");
    }
  } catch {
    child.kill("SIGTERM");
  }
}
