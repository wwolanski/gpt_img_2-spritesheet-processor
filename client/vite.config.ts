import { defineConfig } from "vite";
import { assetPipelinePlugin } from "./server/assetPipelineApi";

function envLimit(name: string, fallback: number): number {
  const value = Number(process.env[name] ?? fallback);
  return Number.isInteger(value) && value > 0 ? value : fallback;
}

export default defineConfig({
  plugins: [assetPipelinePlugin()],
  server: {
    host: process.env.ASSET_PIPELINE_HOST || "127.0.0.1",
    port: envLimit("ASSET_PIPELINE_PORT", 5174),
    strictPort: true,
  },
});
