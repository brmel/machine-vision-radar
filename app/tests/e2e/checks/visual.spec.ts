import { existsSync } from "node:fs";
import { test, expect } from "@playwright/test";
import { MESSAGES, inLocale } from "../../messages.ts";
import { PAGES, VIEWS, show } from "../sample.ts";

const WIDTHS = { desktop: { width: 1280, height: 900 }, mobile: { width: 375, height: 812 } } as const;
const FITS = { phone: WIDTHS.mobile, tablet: { width: 768, height: 1024 }, desktop: WIDTHS.desktop } as const;
const THEMES = ["light", "dark"] as const;

for (const [device, viewport] of Object.entries(WIDTHS)) {
  for (const theme of THEMES) {
    test.describe(`Visual (${device}, ${theme})`, () => {
      test.use({ viewport });
      for (const [name, path] of VIEWS) {
        const baseline = `${name}-${device}${theme === "dark" ? "-dark" : ""}.png`;
        test(`${name} matches its baseline`, async ({ page }, testInfo) => {
          const file = testInfo.snapshotPath(baseline, { kind: "screenshot" });
          const writing = testInfo.config.updateSnapshots === "all" || testInfo.config.updateSnapshots === "changed";
          test.skip(!writing && !existsSync(file),
            `no ${process.platform} baseline (${file}): the comparison is skipped, not passed`);
          await show(page, path, "en", theme);
          await expect(page).toHaveScreenshot(baseline, { fullPage: true, maxDiffPixelRatio: 0.01 });
        });
      }
    });
  }
}

const TAPPABLE =
  "button, select, input:not([type=checkbox]):not([type=radio]), summary, [role=switch], nav a, footer a";

for (const [size, viewport] of Object.entries(FITS)) for (const locale of ["en", "fr"] as const) {
  test.describe(`Fit on ${size} (${locale})`, () => {
    test.use({ viewport, hasTouch: size !== "desktop" });
    for (const [name, path] of VIEWS) {
      test(`${name} neither scrolls sideways, cuts text nor breaks a word`, async ({ page }) => {
        await show(page, path, locale);
        expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth))
          .toBeLessThanOrEqual(0);
        const cut = await page.locator("body *").evaluateAll((elements) =>
          elements
            .filter((el) => el.clientWidth > 1 && el.scrollWidth > el.clientWidth &&
              (getComputedStyle(el).textOverflow === "ellipsis"
                || ["hidden", "clip"].includes(getComputedStyle(el).overflowX)))
            .map((el) => el.textContent?.trim()),
        );
        expect(cut).toEqual([]);
        expect(await page.locator("main").evaluateAll(wordsBrokenMidWord)).toEqual([]);
        expect(await page.locator(".source-chip").evaluateAll(textsOnTwoLines)).toEqual([]);
        const clipped = await page.locator("input[placeholder]").evaluateAll((inputs: HTMLInputElement[]) => {
          const canvas = document.createElement("canvas").getContext("2d");
          if (!canvas) throw new Error("no 2D canvas to measure placeholders with");
          return inputs
            .filter((input) => input.offsetParent !== null)
            .filter((input) => {
              const style = getComputedStyle(input);
              canvas.font = style.font;
              return canvas.measureText(input.placeholder)
                .width > input.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
            })
            .map((input) => input.placeholder);
        });
        expect(clipped).toEqual([]);
        if (size === "desktop") return;
        const small = await page.locator(TAPPABLE).evaluateAll((els) =>
          els
            .filter((el) => {
              const box = el.getBoundingClientRect();
              return box.width > 1 && box.height > 1 && !el.closest("table") && box.height < 44;
            })
            .map((el) =>
              `${el.tagName.toLowerCase()} ${Math.round(el.getBoundingClientRect().height)}px: ${el.textContent?.trim()
                .slice(0, 30) || el.getAttribute("aria-label")}`),
        );
        expect(small).toEqual([]);
      });
    }
  });
}

const DEFAULT = { accent: "rgb(255, 210, 30)", light: "rgb(248, 250, 252)", dark: "rgb(9, 13, 20)" };
const FIXTURE = { accent: "rgb(0, 120, 200)", light: "rgb(255, 245, 235)", dark: "rgb(30, 10, 40)" };
const FIXTURE_THEME =
  `:root { --color-accent: ${FIXTURE.accent}; --color-page: ${FIXTURE.light}; } .dark { --color-page: ${FIXTURE.dark}; `
    + `} * { transition: none !important; }`;

for (const theme of THEMES) {
  test(`a fixture theme restyles every view (${theme})`, async ({ page }) => {
    for (const [, path] of VIEWS) {
      await show(page, path, "en", theme);
      await page.addStyleTag({ content: FIXTURE_THEME });
      const colors = await page.locator("body, body *").evaluateAll((elements) =>
        elements.flatMap((el) => {
          const style = getComputedStyle(el);
          return [style.color, style.backgroundColor, style.borderTopColor, style.borderBottomColor, style.outlineColor,
            style.fill, style.stroke];
        }),
      );
      expect(colors.filter((c) => c === DEFAULT.accent || c === DEFAULT[theme]), path).toEqual([]);
      expect(colors, path).toContain(FIXTURE[theme]);
    }
  });
}

test("the favicon draws the header's mark", async ({ page }) => {
  await show(page, "/", "en", "light");
  const colors = await page.evaluate(async () => {
    const canvas = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
    if (!canvas) throw new Error("no 2D canvas to read colors with");
    const rgb = (color: string) => {
      canvas.clearRect(0, 0, 1, 1);
      canvas.fillStyle = color;
      canvas.fillRect(0, 0, 1, 1);
      return [...canvas.getImageData(0, 0, 1, 1).data].join(",");
    };
    const tile = document.querySelector("header a[href='/'] > span");
    const favicon = document.createElement("div");
    favicon.innerHTML = await (await fetch("/favicon.svg")).text();
    document.body.append(favicon);
    const paint = (svg: Element | null | undefined, selector: string, property: "fill" | "stroke") => {
      const el = svg?.querySelector(selector);
      if (!el) throw new Error(`no ${selector} in the mark`);
      return rgb(getComputedStyle(el)[property]);
    };
    const glyph = (svg: Element | null | undefined) =>
      [paint(svg, "circle", "stroke"), paint(svg, "path", "fill"), paint(svg, "circle:last-of-type", "fill")];
    if (!tile) throw new Error("no brand mark in the header");
    return { header: [rgb(getComputedStyle(tile).backgroundColor), ...glyph(tile.querySelector("svg"))],
      favicon: [paint(favicon, "rect", "fill"), ...glyph(favicon)] };
  });
  expect(colors.favicon).toEqual(colors.header);
});

for (const [size, viewport] of Object.entries(FITS)) {
  test(`a long pagination fits on ${size}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await inLocale(page, "fr");
    await page.route("**/documents:runAggregationQuery", (route) =>
      route.fulfill({ json: [{ result: { aggregateFields: { total: { integerValue: "820" } } } }] }));
    await page.goto("/browse");
    await expect(page.getByRole("navigation", { name: MESSAGES.fr.paginationLabel })).toContainText("41");
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  });
}

function textsOnTwoLines(roots: Element[]): string[] {
  return roots.flatMap((root) => {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const broken: string[] = [];
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const range = document.createRange();
      range.selectNodeContents(node);
      const lines = new Set([...range.getClientRects()].filter((r) => r.width > 1).map((r) => Math.round(r.top)));
      if (lines.size > 1) broken.push(node.textContent ?? "");
    }
    return broken;
  });
}

function wordsBrokenMidWord(roots: Element[]): string[] {
  const block = (el: Element | null): Element | null =>
    (el && getComputedStyle(el).display.startsWith("inline") ? block(el.parentElement) : el);
  return roots.flatMap((root) => {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const broken: string[] = [];
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.textContent ?? "";
      const line = block(node.parentElement)?.getBoundingClientRect().width ?? 0;
      const rects = (from: number, to: number) => {
        const range = document.createRange();
        range.setStart(node, from);
        range.setEnd(node, to);
        return [...range.getClientRects()].filter((r) => r.width > 0);
      };
      const top = (at: number) => rects(at, at + 1)[0]?.top ?? 0;
      for (const { 0: word, index: start } of text.matchAll(/\S+/g)) {
        const parts = rects(start, start + word.length);
        if (parts.length < 2 || parts.reduce((width, r) => width + r.width, 0) >= line) continue;
        if ([...word].some((_, i) => i > 0 && !"-/".includes(word[i - 1]) && top(start + i) > top(start + i - 1) + 2)) {
          broken.push(word);
        }
      }
    }
    return broken;
  });
}

for (const locale of ["en", "fr"] as const) {
  test(`agents and a product's sources keep their words whole on a phone (${locale})`, async ({ page }) => {
    const T = MESSAGES[locale];
    await page.setViewportSize(WIDTHS.mobile);
    await show(page, "/agents", locale);
    expect(await page.locator("main").evaluateAll(wordsBrokenMidWord)).toEqual([]);
    await show(page, PAGES.sources, locale);
    await page.getByRole("group", { name: T.productTabsLabel })
      .getByRole("button", { name: new RegExp(`^${T.tabSources}`) }).click();
    await expect(page.locator("main a[href^='http']").first()).toBeVisible();
    expect(await page.locator("main").evaluateAll(wordsBrokenMidWord)).toEqual([]);
  });
}
