type LogContext = Record<string, unknown>;
type LogLevel = "info" | "warn" | "error";

function write(level: LogLevel, event: string, context: LogContext = {}): void {
  const entry = {
    timestamp: new Date().toISOString(),
    level,
    service: "asset-pipeline-api",
    event,
    ...context,
  };
  const line = JSON.stringify(entry);
  if (level === "error") {
    console.error(line);
  } else if (level === "warn") {
    console.warn(line);
  } else {
    console.info(line);
  }
}

export const logger = {
  info: (event: string, context?: LogContext): void => write("info", event, context),
  warn: (event: string, context?: LogContext): void => write("warn", event, context),
  error: (event: string, context?: LogContext): void => write("error", event, context),
};
