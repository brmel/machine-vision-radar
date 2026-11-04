import type { Page } from "@playwright/test";
import type { ProductView } from "../../src/domain/views.ts";
import { productPath } from "../../src/domain/paths.ts";
import { compareQuery } from "../../src/domain/compare.ts";
import { DEFAULT_MESSAGES as messages } from "../../src/shell/i18n/messages.ts";

export type Step =
  | { goto: string }
  | { click: { role: "button" | "link"; name: string } }
  | { fill: { label: string; text: string } }
  | { scroll: number }
  | { hold: number }
  | { still: string };

const READ_MS = 3500;

export const reading = (path: string): Step[] => [
  { goto: path }, { hold: READ_MS }, { still: "top" }, { scroll: 600 }, { hold: READ_MS }, { still: "middle" },
  { scroll: 600 }, { hold: READ_MS },
];

export const sourcing = (product: ProductView): Step[] => [
  { goto: productPath(product.slug) }, { hold: READ_MS }, { still: "specs" }, { scroll: 500 }, { hold: READ_MS },
  { click: { role: "button", name: messages.tabSources } }, { hold: READ_MS }, { still: "sources" },
];

export const asking = (question: string): Step[] => [
  { goto: "/search" }, { fill: { label: messages.askTitle, text: question } }, { hold: 1500 },
  { click: { role: "button", name: messages.askAction } }, { hold: 3 * READ_MS }, { still: "answer" },
];

export const comparing = (product: ProductView, other: ProductView): Step[] =>
  reading(`/compare?${compareQuery([product.id, other.id], false)}`);

export const heldFor = (steps: readonly Step[]): number =>
  steps.reduce((ms, step) => ms + ("hold" in step ? step.hold : 0), 0) / 1000;

export async function play(page: Page, steps: readonly Step[], prefix: string): Promise<{ stills: string[];
  shown: number }> {
  const started = Date.now();
  let shown: number | undefined;
  const stills: string[] = [];
  for (const step of steps) {
    if ("goto" in step) {
      await page.goto(step.goto);
      await page.getByRole("heading", { level: 1 }).first().waitFor();
      await page.waitForLoadState("networkidle");
      shown ??= (Date.now() - started) / 1000;
    } else if ("click" in step) await page.getByRole(step.click.role, { name: step.click.name }).first().click();
    else if ("fill" in step) await page.getByLabel(step.fill.label).first().fill(step.fill.text);
    else if ("scroll" in step) await page.mouse.wheel(0, step.scroll);
    else if ("hold" in step) await page.waitForTimeout(step.hold);
    else {
      const file = `${prefix}-${step.still}.png`;
      await page.screenshot({ path: file });
      stills.push(file);
    }
  }
  return { stills, shown: shown ?? 0 };
}
