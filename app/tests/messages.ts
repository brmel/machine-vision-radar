import { test, type BrowserContext, type Page } from "@playwright/test";

export { MESSAGES } from "../scripts/prerender/language.ts";

export const inLocale = (target: Page | BrowserContext, locale: string, theme?: "light" | "dark"): Promise<unknown> =>
  target.addInitScript(([l, t]) => {
    localStorage.setItem("machineVisionRadar.locale", l);
    if (t) localStorage.setItem("machineVisionRadar.themePreference", t);
  }, [locale, theme] as const);

export function inEachLocale(title: string, body: (locale: "en" | "fr") => void): void {
  for (const locale of ["en", "fr"] as const) {
    test.describe(`${title} (${locale})`, () => {
      test.beforeEach(({ page }) => inLocale(page, locale));
      body(locale);
    });
  }
}
