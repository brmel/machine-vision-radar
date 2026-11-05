import { test, expect, type Locator, type Page } from "@playwright/test";
import { PAGES, cardsOf, category, choiceFacets, escape, facetLabel, facetsOf, index, label, numberFacet,
  specLabel } from "../sample.ts";
import { MESSAGES, inEachLocale, inLocale } from "../../messages.ts";

const [facet] = choiceFacets;
const option = facet.options[0];
const bound = ((numberFacet.min ?? 0) + (numberFacet.max ?? 0)) / 2 + 0.5;
const ends = cardsOf(category.id).flatMap((c) => {
  const v = c.specs[numberFacet.spec_key];
  return v === undefined ? [] : "quantity" in v ? [[v.quantity.value, v.quantity.value]] : "range" in v
    ? [[v.range.min, v.range.max]] : [];
});
const kept = {
  min: ends.filter(([, high]) => high >= bound).length,
  max: ends.filter(([low]) => low <= bound).length,
};
const numeric = category.sections.core.findIndex((key) => cardsOf(category.id)
  .some((c) => c.specs[key] && ("quantity" in c.specs[key] || "range" in c.specs[key])));
const columnKey = category.sections.core[numeric];

async function columnNumbers(page: Page): Promise<(number | null)[]> {
  const cells = await page.getByRole("table").locator(`tbody tr > :nth-child(${numeric + 3})`).allInnerTexts();
  return cells.map((text) => {
    const found = /-?\d+(?:[.,]\d+)?/.exec(text);
    return found ? Number(found[0].replace(",", ".")) : null;
  });
}

const ordered = (values: (number | null)[], desc: boolean): boolean => {
  const known = values.filter((v): v is number => v !== null);
  return values.slice(0, known.length).every((v) => v !== null)
    && known.every((v, i) => i === 0 || (desc ? known[i - 1] >= v : known[i - 1] <= v));
};

async function optionCount(option: Locator): Promise<number> {
  return Number((await option.innerText()).match(/(\d+)\s*$/)?.[1]);
}

async function shownState(page: Page, applied: string): Promise<{ chips: string[]; count: string }> {
  await page.waitForLoadState("networkidle");
  return {
    chips: await page.getByRole("group", { name: applied }).getByRole("button").allInnerTexts(),
    count: await page.getByRole("status").first().innerText(),
  };
}

inEachLocale("Browse filters", (locale) => {
  const t = MESSAGES[locale];
  const count = (n: number) => (new Intl.PluralRules(locale).select(n) === "one" ? t.productCountOne
    : t.productCountOther).replace("{count}", String(n));
  const categoryName = label(category.label, locale);
  const categoryChip = t.appliedFilter.replace("{facet}", t.filterByCategory).replace("{option}", categoryName);
  const bounds = { min: t.rangeFrom, max: t.rangeTo };
  const optionName = label(option.label, locale);

  test("a row names its vendor and product, then its category and core specs, with its compare "
    + "button", async ({ page }) => {
    await page.goto("/browse");
    const row = page.locator("main").getByRole("article").first();
    const name = (await row.getByRole("heading").innerText()).trim();
    const card = cardsOf(category.id).find((c) => c.name === name);
    if (!card) throw new Error(`no card named ${name}`);
    await expect(row.getByRole("link", { name: card.vendor_name, exact: true }))
      .toHaveAttribute("href", `/vendor/${card.vendor}`);
    await expect(row.getByRole("heading").getByRole("link")).toHaveAttribute("href", `/product/${card.slug}`);
    await expect(row.getByText(categoryName, { exact: true })).toBeVisible();
    const core = category.sections.core.filter((key) => key in card.specs && key in index.spec_definitions).slice(0, 3);
    await expect(row.locator("dt")).toHaveText(core.map((key) => label(index.spec_definitions[key].label, locale)));
    await expect(row.getByRole("button", { name: t.compareAction, exact: true })).toBeVisible();

    await page.goto(PAGES.browse);
    const hubRow = page.locator("main").getByRole("article").first();
    await expect(hubRow.getByRole("heading")).toBeVisible();
    await expect(hubRow.getByText(categoryName, { exact: true })).toHaveCount(0);
  });

  test("categories sit under their domain, and a filter group resets alone", async ({ page }) => {
    await page.goto("/browse");
    const aside = page.locator("aside");
    const domain = index.domains.find((d) => d.id === category.domain);
    await expect(aside.getByRole("group", { name: t.filterByCategory, exact: true }))
      .toContainText(label(domain?.label ?? { en: "" }, locale));
    const applied = page.getByRole("group", { name: t.appliedFiltersLabel }).getByRole("button", { name: /:/ });
    await aside.getByRole("group", { name: t.filterByDomain, exact: true }).getByRole("button").first().click();
    await expect(applied).toHaveCount(1);
    await aside.getByRole("group", { name: t.filterByPipeline, exact: true }).getByRole("button").first().click();
    await expect(applied).toHaveCount(2);
    await aside.locator(":scope > div")
      .filter({ has: page.getByRole("heading", { name: t.filterByDomain, exact: true }) })
        .getByRole("button", { name: t.facetReset }).click();
    await expect(applied).toHaveCount(1);
    await expect(applied).toContainText(t.filterByPipeline);

    await page.goto(PAGES.browse);
    const group = aside.getByRole("group", { name: t.tabSpecs }).locator(":scope > div")
      .filter({ has: page.getByRole("heading", { name: facetLabel(facet, locale), exact: true }) });
    await group.getByRole("button", { name: new RegExp(`^${escape(optionName)}\\s*\\d+$`) }).click();
    await expect(applied).toHaveCount(2);
    await group.getByRole("button", { name: t.facetReset }).click();
    await expect(applied).toHaveCount(1);
    await expect(applied).toContainText(categoryChip);
  });

  test("on a phone the filters open full screen over the compare tray, and close from their close button, the list "
    + "unchanged, or from their button with the count", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/browse");
    await page.locator("main").getByRole("article").first()
      .getByRole("button", { name: t.compareAction, exact: true }).click();
    const tray = page.getByText(t.compareTrayCount.replace("{count}", "1"));
    await expect(tray).toBeVisible();
    const trayOnTop = () => tray.evaluate((el) => {
      const box = el.getBoundingClientRect();
      return el.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2));
    });
    const list = page.url();
    const toggle = page.getByRole("button", { name: t.filtersTitle });
    const aside = page.locator("aside");
    await toggle.click();
    expect(await aside.boundingBox()).toMatchObject({ x: 0, y: 0, width: 375 });
    expect(await trayOnTop()).toBe(false);
    await aside.getByRole("button", { name: t.filtersClose }).click();
    await expect(aside).toBeHidden();
    expect([page.url(), await trayOnTop()]).toEqual([list, true]);
    await toggle.click();
    await aside.getByRole("button",
      { name: new RegExp(`^${escape(t.filtersShowOther).replace("\\{count\\}", "\\d+")}$`) }).click();
    await expect(aside).toBeHidden();
  });

  test("two filters give two chips and a count equal to the cards; removing one updates the "
    + "count", async ({ page }) => {
    await page.goto("/browse");
    const aside = page.locator("aside");
    const chip = aside.getByRole("button", { name: new RegExp(`^${escape(categoryName)}\\s*\\d+$`) });
    const categoryCount = await optionCount(chip);
    await chip.click();
    await expect(page.getByRole("status").first()).toHaveText(count(categoryCount));
    const facets = facetsOf(category.id).filter((f) => f.options.length > 0);
    expect(facets.map((f) => f.count)).toEqual(facets.map((f) => f.count).sort((a, b) => b - a));
    await expect(aside.getByRole("group", { name: facetLabel(facets[0], locale) })).toBeVisible();

    const options = aside.getByRole("group", { name: t.tabSpecs }).getByRole("button", { pressed: false });
    const counts = await Promise.all((await options.all()).map(optionCount));
    const pick = counts.indexOf(Math.min(...counts));
    await options.nth(pick).click();

    const applied = page.getByRole("group", { name: t.appliedFiltersLabel });
    await expect(applied.getByRole("button", { name: /:/ })).toHaveCount(2);
    await expect(applied).toContainText(categoryChip);
    await expect(page.getByRole("status").first()).toHaveText(count(counts[pick]));
    await expect(page.locator("main").getByRole("article")).toHaveCount(counts[pick]);
    await expect(aside.locator("span").filter({ hasText: /^0$/ })).toHaveCount(0);
    await expect(aside).not.toContainText(/Compatibilit[yé]/);

    await applied.getByRole("button", { name: /:/ }).filter({ hasNotText: categoryChip }).click();
    await expect(applied.getByRole("button", { name: /:/ })).toHaveCount(1);
    await expect(page.getByRole("status").first()).toHaveText(count(categoryCount));
    await expect(aside.locator("span").filter({ hasText: /^0$/ })).toHaveCount(0);
    await applied.getByRole("button", { name: t.clearAll }).click();
    await expect(page).toHaveURL(/\/browse$/);
  });

  for (const end of ["min", "max"] as const) {
    test(`a number facet's ${end} bound, typed as the locale writes decimals, filters in its unit and stays across `
      + `reload and back`, async ({ page }) => {
      expect(kept[end]).toBeLessThan(category.products);
      await page.goto(PAGES.browse);
      await expect(page.locator("aside").getByRole("heading", { name: facetLabel(numberFacet, locale) }))
        .toHaveAttribute("title", label(numberFacet.description!, locale));
      const typed = locale === "fr" ? String(bound).replace(".", ",") : String(bound);
      const box = page.locator("aside")
        .getByRole("textbox", { name: `${facetLabel(numberFacet, locale)}, ${bounds[end]}` });
      await box.fill(typed);
      await box.press("Enter");
      await expect(page).toHaveURL(new RegExp(`${escape(numberFacet.spec_key)}_${end}=${escape(String(bound))}$`));
      await expect(page.getByRole("status").first()).toHaveText(count(kept[end]));
      await page.reload();
      await expect(page.getByRole("status").first()).toHaveText(count(kept[end]));
      await expect(page.locator("aside")
        .getByRole("textbox", { name: `${facetLabel(numberFacet, locale)}, ${bounds[end]}` })).toHaveValue(typed);
      await page.goBack();
      await expect(page.getByRole("status").first()).toHaveText(count(category.products));
    });
  }

  test("the table view lists the core specs and sorts on a column both ways, kept in the URL", async ({ page }) => {
    await page.goto(PAGES.browse);
    await page.getByRole("group", { name: t.layoutLabel }).getByRole("button", { name: t.layoutTable }).click();
    await expect(page).toHaveURL(/view=table$/);
    const header = page.getByRole("table").getByRole("columnheader", { name: specLabel(columnKey, locale) });
    await header.getByRole("button").click();
    await expect(page).toHaveURL(new RegExp(`sort=${escape(columnKey)}&view=table$`));
    await expect(header).toHaveAttribute("aria-sort", "ascending");
    expect(ordered(await columnNumbers(page), false)).toBe(true);
    await header.getByRole("button").click();
    await expect(page).toHaveURL(new RegExp(`sort=${escape(columnKey)}-desc&view=table$`));
    await expect(header).toHaveAttribute("aria-sort", "descending");
    const descending = await columnNumbers(page);
    expect(ordered(descending, true)).toBe(true);
    await page.reload();
    await expect.poll(() => columnNumbers(page)).toEqual(descending);
  });

  test("reload, back, forward and a fresh browser give the same chips and count", async ({ page, browser }) => {
    await page.goto(PAGES.browse);
    const aside = page.locator("aside");
    const facetGroup = aside.getByRole("group", { name: facetLabel(facet, locale), exact: true });
    await facetGroup.getByRole("button", { name: new RegExp(`^${escape(optionName)}\\s*\\d+$`) }).click();
    await expect(page).toHaveURL(new RegExp(`${escape(facet.spec_key)}=${escape(option.id)}$`));
    const one = await shownState(page, t.appliedFiltersLabel);
    await aside.getByRole("group", { name: t.tabSpecs }).getByRole("group").filter({ hasNotText: optionName })
      .getByRole("button", { pressed: false }).first().click();
    await expect(page.getByRole("group", { name: t.appliedFiltersLabel }).getByRole("button", { name: /:/ }))
      .toHaveCount(3);
    const two = await shownState(page, t.appliedFiltersLabel);
    const url = page.url();
    expect(new URL(url).pathname).toBe(`/category/${category.id}`);
    expect(new URL(url).search).toMatch(/^\?[a-z_]+=[^&%]+&[a-z_]+=[^&%]+$/);
    expect(url).toContain(`${facet.spec_key}=${option.id}`);

    await page.reload();
    expect(await shownState(page, t.appliedFiltersLabel)).toEqual(two);
    await page.goBack();
    expect(await shownState(page, t.appliedFiltersLabel)).toEqual(one);
    await page.goForward();
    expect(await shownState(page, t.appliedFiltersLabel)).toEqual(two);

    const fresh = await browser.newContext();
    await inLocale(fresh, locale);
    const other = await fresh.newPage();
    await other.goto(url);
    expect(await shownState(other, t.appliedFiltersLabel)).toEqual(two);
    await fresh.close();
  });
});
