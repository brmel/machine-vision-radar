import { test, expect, type Page } from "@playwright/test";
import { escape, index, specLabel, view } from "../sample.ts";
import { MESSAGES, inEachLocale } from "../../messages.ts";

const values = (id: string): Map<string, string> => {
  const v = view(id);
  return new Map([...v.core, ...v.detail].filter((c) => c.value).map((c) => [c.key, JSON.stringify(c.value)]));
};
const isNumber = (vals: Map<string, string>, key: string): boolean =>
  /^\{"quantity":\{"value":-?[\d.]+/.test(vals.get(key) ?? "");

function pick(): { ids: string[]; key: string } {
  for (const c of index.categories) {
    const members = index.products.filter((p) => p.category === c.id).map((p) => ({ id: p.id, vals: values(p.id) }));
    for (const key of c.sections.core) {
      for (const a of members.filter((p) => isNumber(p.vals, key))) {
        const b = members.find((p) => isNumber(p.vals, key) && p.vals.get(key) !== a.vals.get(key)
          && [...a.vals].some(([k, v]) => p.vals.get(k) === v));
        if (b) return { ids: [a.id, b.id], key };
      }
    }
  }
  throw new Error("no two products that differ on a core quantity spec and agree on another");
}
const { ids, key } = pick();

async function rows(page: Page): Promise<{ label: string; equal: boolean }[]> {
  return page.locator("tbody tr").filter({ has: page.locator('th[scope="row"]') }).evaluateAll((trs) =>
    trs.map((tr) => {
      const cells =
        [...tr.querySelectorAll("td")].map((td) => (td.querySelector("span > span") ?? td).textContent?.trim());
      return { label: tr.querySelector("th")?.textContent?.trim() ?? "", equal: cells.every((c) => c === cells[0]) };
    }),
  );
}

inEachLocale("Compare", (locale) => {
  const t = MESSAGES[locale];
  const rowLabel = specLabel(key, locale);

  test("chips in every valued cell, and only differences hides equal rows", async ({ page }) => {
    await page.goto(`/compare?ids=${ids.join(",")}`);

    await expect(page.getByRole("columnheader", { name: t.specSectionCore })).toBeVisible();
    const quantityRow = page.getByRole("row", { name: new RegExp(`^${escape(rowLabel)}`) });
    await expect(quantityRow.getByRole("cell")).toHaveCount(2);
    for (const cell of await quantityRow.getByRole("cell").all()) await expect(cell).toHaveText(/^[\d\s.,–-]+\S.*·/);
    expect(index.spec_definitions[key].better).toBe("higher");
    const [a, b] =
      ids.map((id) => (JSON.parse(values(id).get(key) ?? "{}") as { quantity: { value: number } }).quantity.value);
    await expect(quantityRow.getByRole("cell").nth(a > b ? 0 : 1)).toContainText(t.compareHighest);
    await expect(quantityRow.getByRole("cell").nth(a > b ? 1 : 0)).not.toContainText(t.compareHighest);

    const specCells = page.locator("tbody tr").filter({ has: page.locator('th[scope="row"]') }).locator("td");
    for (const cell of await specCells.all()) {
      const text = (await cell.innerText()).trim();
      if (text === t.unknownValue) await expect(cell.locator(".source-chip")).toHaveCount(0);
      else if (await cell.locator(".source-chip").count() === 0) expect(await cell.evaluate((td) =>
        td.closest("tr")?.querySelector("th")?.textContent)).toMatch(/Domain|Category|Domaine|Catégorie/);
    }

    const before = await rows(page);
    const differing = before.filter((r) => !r.equal).map((r) => r.label);
    expect(differing).toContain(rowLabel);

    await page.getByRole("checkbox", { name: t.onlyDifferencesToggle }).check();
    await expect(page).toHaveURL(/[?&]diff=1/);
    expect((await rows(page)).map((r) => r.label)).toEqual(differing);

    await page.reload();
    await expect(page.getByRole("checkbox", { name: t.onlyDifferencesToggle })).toBeChecked();
    expect((await rows(page)).map((r) => r.label)).toEqual(differing);
  });

  test("on a phone, two products read side by side with nothing cut or scrolled", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto(`/compare?ids=${ids.join(",")}`);
    await expect(page.locator("thead th")).toHaveCount(3);
    const quantityRow = page.getByRole("row", { name: new RegExp(`^${escape(rowLabel)}`) });
    await expect(quantityRow.getByText(t.compareHighest)).toBeVisible();
    const table = page.locator("table").locator("..");
    expect(await table.evaluate((el) => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
    expect(await page.locator("table td *, table thead th *").evaluateAll((els) => els
      .filter((el) => el.scrollWidth > el.clientWidth + 1).map((el) => el.textContent))).toEqual([]);
  });
});
