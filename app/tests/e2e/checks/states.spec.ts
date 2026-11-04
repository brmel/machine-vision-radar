import { test, expect, type Page, type Route } from "@playwright/test";
import type { MessageKey } from "../../../src/shell/i18n/messages.ts";
import { BRAND_CONFIG } from "../../../src/ui/theme/brand.ts";
import { MESSAGES, inEachLocale } from "../../messages.ts";
import { EMPTY, PAGES } from "../sample.ts";

const FIRESTORE = "**/v1/projects/**";
const FIND = "**/api/find";
const REGISTRY = "**/registry.json";

type View = { name: keyof typeof EMPTY; empty: MessageKey; error?: MessageKey };

const VIEWS: readonly View[] = [
  { name: "browse", empty: "noMatchingProducts" },
  { name: "search", empty: "noMatchingProducts", error: "searchErrorTitle" },
  { name: "product", empty: "productNotFound" },
  { name: "history", empty: "historyEmpty" },
  { name: "vendor", empty: "noVendorProducts" },
  { name: "compare", empty: "compareEmptyTitle" },
  { name: "news", empty: "newsNoneOfKind" },
  { name: "article", empty: "articleNotFound" },
];

const hold = (): void => undefined;
const refuse = (route: Route): Promise<void> => route.abort("connectionrefused");

async function open(page: Page, name: View["name"], handler: (route: Route) => unknown): Promise<void> {
  if (name !== "product") {
    await page.route(FIRESTORE, handler);
    await page.route(FIND, handler);
    await page.goto(PAGES[name]);
    return;
  }
  await page.goto("/browse");
  const card = page.getByRole("main").getByRole("article").first().getByRole("heading").getByRole("link");
  await expect(card).toBeVisible();
  await page.route(FIRESTORE, handler);
  await card.click();
}

inEachLocale("States", (locale) => {
  const t = MESSAGES[locale];
  const loads = async (page: Page): Promise<void> => {
    await expect(page.getByRole("status").filter({ hasText: t.loading })).toBeAttached();
    await page.unrouteAll({ behavior: "ignoreErrors" });
  };
  const retry = async (page: Page): Promise<void> => {
    await page.unrouteAll({ behavior: "ignoreErrors" });
    await page.getByRole("button", { name: t.errorRetry }).click();
  };

  for (const view of VIEWS) {
    test(`${view.name} shows loading, empty and error states`, async ({ page }) => {
      await open(page, view.name, hold);
      await loads(page);

      await page.evaluate(() => localStorage.removeItem("machineVisionRadar.comparedIds"));
      await page.goto(EMPTY[view.name]);
      await expect(page.getByRole("heading", { name: t[view.empty] })).toBeVisible();

      await open(page, view.name, refuse);
      await expect(page.getByRole("alert").getByRole("heading", { name: t[view.error ?? "errorTitle"] })).toBeVisible();
      await retry(page);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByRole("alert")).toHaveCount(0);
    });
  }

  test("the shell shows loading, then an error whose retry recovers", async ({ page }) => {
    await page.route(REGISTRY, hold);
    await page.goto("/about");
    await loads(page);

    await page.route(REGISTRY, refuse);
    await page.goto("/about");
    await expect(page.getByRole("heading", { level: 1, name: t.errorTitle })).toBeVisible();
    await retry(page);
    await expect(page.getByRole("heading", { level: 1 }))
      .toHaveText(t.aboutTitle.replace("{brand}", BRAND_CONFIG.wordmark));
  });
});
