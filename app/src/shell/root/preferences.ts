import { logger } from "../logger.ts";

export function stored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch (err) {
    logger.warn("a saved preference is not readable; the default stands", { key }, err);
    return null;
  }
}

export function save(key: string, value: string, warning: string): void {
  try {
    localStorage.setItem(key, value);
  } catch (err) {
    logger.warn(warning, { key }, err);
  }
}
