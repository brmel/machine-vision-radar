import type { ProductView } from "../../domain/views.ts";
import { MAX_COMPARED } from "../../domain/compare.ts";
import { embeddedProduct } from "../../adapters/read-model/embedded.ts";
import { COMPARED_KEY } from "../../features/compare/useComparedIds.ts";
import { LOCALE_KEY } from "../i18n/index.tsx";
import { THEME_KEY, type ThemePreference } from "../layout/ThemeProvider.tsx";
import type { Route } from "../routing/routes.ts";
import { routeFromPath } from "../routing/router.ts";
import { logger } from "../logger.ts";
import { stored } from "./preferences.ts";

export interface Start {
  route: Route;
  preferred: readonly string[];
  theme: ThemePreference;
  compared: readonly string[];
  prerendered: ProductView | null;
}

function theme(): ThemePreference {
  const saved = stored(THEME_KEY);
  return saved === "light" || saved === "dark" ? saved : "system";
}

function compared(): string[] {
  const fromUrl = (new URLSearchParams(window.location.search).get("ids") ?? "").split(",").map((s) => s.trim())
    .filter(Boolean);
  if (fromUrl.length > 0) return fromUrl.slice(0, MAX_COMPARED);
  try {
    const parsed: unknown = JSON.parse(stored(COMPARED_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string").slice(0, MAX_COMPARED) : [];
  } catch (err) {
    logger.warn("saved compare selection not readable; starting empty", { key: COMPARED_KEY }, err);
    return [];
  }
}

export function browserStart(): Start {
  return {
    route: routeFromPath(window.location.pathname, window.location.search),
    preferred: [stored(LOCALE_KEY), navigator.language.slice(0, 2).toLowerCase()].filter((code): code is string =>
      code !== null),
    theme: theme(),
    compared: compared(),
    prerendered: embeddedProduct(document),
  };
}
