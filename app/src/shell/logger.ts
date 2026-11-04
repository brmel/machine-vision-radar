type Fields = Readonly<Record<string, string | number | boolean | null>>;
type Level = "info" | "warn" | "error";

export const LOG_RULES = {
  fields: ["time", "level", "event", "correlation_id"],
  levels: ["debug", "info", "warn", "error"],
  redacted: "[redacted]",
  secret_key: "(^|[_-])(token|secret|password|authorization|cookie|api_?key|credentials?)$",
  secret_values: [
    "bearer\\s+[0-9a-z._~+/-]+=*",
    "ya29\\.[0-9a-z_-]+",
    "AIza[0-9a-z_-]{35}",
    "eyJ[0-9a-z_-]+\\.[0-9a-z_-]+\\.[0-9a-z_-]+",
    "mvr_[0-9a-z]{20,}",
  ],
};
const SECRET_KEY = new RegExp(LOG_RULES.secret_key, "i");
const SECRET_VALUE = new RegExp(LOG_RULES.secret_values.join("|"), "gi");
const CORRELATION_ID = crypto.randomUUID();

function redact(fields: Fields): Fields {
  return Object.fromEntries(
    Object.entries(fields).map(([key, value]) => [key, SECRET_KEY.test(key) ? LOG_RULES.redacted
      : typeof value === "string" ? value.replace(SECRET_VALUE, LOG_RULES.redacted) : value]),
  );
}

function write(level: Level, event: string, fields: Fields, cause: unknown): void {
  const because: Fields = cause === undefined ? {}
    : { cause: cause instanceof Error ? `${cause.name}: ${cause.message}` : String(cause) };
  console[level](JSON.stringify(redact({ time: new Date().toISOString(), level, event, correlation_id: CORRELATION_ID,
    ...fields, ...because })));
}

export const logger = {
  info: (event: string, fields: Fields = {}): void => write("info", event, fields, undefined),
  warn: (event: string, fields: Fields = {}, cause?: unknown): void => write("warn", event, fields, cause),
  error: (event: string, fields: Fields = {}, cause?: unknown): void => write("error", event, fields, cause),
};
