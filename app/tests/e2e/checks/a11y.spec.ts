import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Locator, type Page } from "@playwright/test";
import { inLocale } from "../../messages.ts";
import { PAGES as SAMPLE, VIEWS, show } from "../sample.ts";

const PAGES = [...VIEWS, ["a hub's table", `${SAMPLE.browse}&view=table`]] as const;

const VIEWPORTS = { desktop: { width: 1280, height: 720 }, mobile: { width: 375, height: 812 } } as const;

for (const [device, viewport] of Object.entries(VIEWPORTS)) {
  for (const locale of ["en", "fr"] as const) {
    for (const theme of ["light", "dark"] as const) {
      test.describe(`Accessibility (${device}, ${locale}, ${theme})`, () => {
        test.use({ viewport });
        for (const [name, path] of PAGES) {
          test(`${name} has no serious or critical axe violation`, async ({ page }) => {
            await show(page, path, locale, theme);
            const { violations } = await new AxeBuilder({ page })
              .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
            const blocking = violations
              .filter((v) => v.impact === "serious" || v.impact === "critical")
              .map((v) => `${v.id} (${v.impact}): ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
            expect(blocking).toEqual([]);
          });
        }
      });
    }
  }
}

async function tabTo(page: Page, target: Locator, max = 80): Promise<void> {
  for (let i = 0; i < max; i++) {
    if (await target.evaluate((el) => el === document.activeElement)) return;
    await page.keyboard.press("Tab");
  }
  throw new Error(`keyboard never reached ${target}`);
}

async function expectVisibleFocus(target: Locator): Promise<void> {
  const visible = await target.evaluate((el) => {
    const drawsRing = (node: Element, pseudo?: string) => {
      const style = getComputedStyle(node, pseudo);
      return (style.outlineStyle !== "none" && style.outlineWidth !== "0px") || style.boxShadow !== "none";
    };
    return drawsRing(el) || drawsRing(el, "::after") || (el.parentElement !== null && drawsRing(el.parentElement));
  });
  expect(visible, "focused element shows a focus indicator").toBe(true);
}

test("keyboard alone reaches the search box, a filter and a product link, each with visible "
  + "focus", async ({ page }) => {
  await inLocale(page, "en", "light");
  await page.goto("/");
  const search = page.getByRole("main").getByRole("textbox").first();
  await tabTo(page, search);
  await expectVisibleFocus(search);

  await page.goto("/browse");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const filter = page.locator("aside").getByRole("button").first();
  const product = page.locator("main").getByRole("article").first().getByRole("heading").getByRole("link");
  for (const target of [filter, product]) {
    await tabTo(page, target);
    await expectVisibleFocus(target);
  }
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/product\//);
});

for (const theme of ["light", "dark"] as const) {
  test(`keyboard alone reaches the product's tabs and its history, each with visible focus `
    + `(${theme})`, async ({ page }) => {
    await show(page, SAMPLE.history.replace(/\/history$/, ""), "en", theme);
    for (const target of [page.getByRole("link", { name: "History" }),
      page.getByRole("button", { name: /^Sources/ })]) {
      await tabTo(page, target);
      await expectVisibleFocus(target);
    }
    await page.keyboard.press("Enter");
    await expect(page.locator("table.sources-table")).toBeVisible();
  });
}

test("with reduced motion asked for, the home's pipeline runs no animation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(await page.evaluate(() => document.getAnimations().length)).toBe(0);
});
