import { test, expect } from "@playwright/test";
import type { SpecCell } from "../../../src/domain/views.ts";
import { BRAND_CONFIG } from "../../../src/ui/theme/brand.ts";
import { escape, index, label, productViews, specLabel } from "../sample.ts";
import { MESSAGES, inEachLocale } from "../../messages.ts";

const quantity = (c: SpecCell) => (c.value && "quantity" in c.value ? c.value.quantity : undefined);
const SUBJECT = productViews.find((v) => v.detail.some((c) => quantity(c)?.value !== undefined && c.group)
  && [...v.core, ...v.detail].some((c) => !c.value));
const RELEASED = productViews.find((v) => v.versions.length > 1 && v.offerings.length > 0);
const RELATED = productViews.filter((v) => v.relations.length > 0 || v.identifiers.length > 0);
const MARKED = productViews.find((v) => v.identifiers.some((i) => i.schema_org));
const ABSENT = productViews.flatMap((v) => [...v.core, ...v.detail].flatMap((c) =>
  (c.value && "none" in c.value ? [[v, c.key, c.value.none] as const] : [])))[0];
const MIXED = productViews.find((v) => v.detail.some((c) => c.value && c.group)
  && v.detail.some((c) => c.value && !c.group));
const DESCRIBED = productViews.find((v) => v.core.some((c) => c.value) && v.summary);
const DESCRIPTION = DESCRIBED?.summary;
const LINKED = productViews.find((v) => v.relations.some((r) => r.schema_org && r.basis === "asserted"));
const DETAIL = SUBJECT?.detail.find((c) => quantity(c)?.value !== undefined && c.group);
const CORE = SUBJECT?.core.find((c) => quantity(c)?.value !== undefined);
if (!SUBJECT || !DETAIL || !CORE || !RELEASED || !MARKED || !LINKED || !ABSENT || !DESCRIBED || !DESCRIPTION
  || !MIXED) {
  throw new Error("the sample needs a product with a core quantity, a grouped detail quantity and an unpublished row, "
    + "releases and offerings, marked identifiers and relations, a value stated as none, a described product, and "
    + "one with rows in a group and in none");
}
const SNAKE = /\b[a-z0-9]+_[a-z0-9_]+\b/;

inEachLocale("Product specs", (locale) => {
  const t = MESSAGES[locale];

  test("one table: the published key rows first, a group's under its name, the unpublished behind one keyboard "
    + "disclosure", async ({ page }) => {
    await page.goto(`/product/${SUBJECT.slug}`);
    const published = (cells: readonly SpecCell[]) => cells.filter((c) => c.value);
    const runs = page.locator("table.spec-table tbody");
    const run = (title: string) => runs
      .filter({ has: page.locator("th", { hasText: new RegExp(`^${escape(title)}$`) }) }).locator("tr:has(td)");
    await expect(runs.first().locator("th")).toHaveText(t.specSectionCore);
    const core = run(t.specSectionCore);
    await expect(core).toHaveCount(published(SUBJECT.core).length);
    await expect(core.filter({ hasText: specLabel(CORE.key, locale) }).getByRole("cell").nth(1))
      .toHaveText(new RegExp(`^${quantity(CORE)?.value}\\D`));

    const all = runs.locator("tr:has(td)");
    await expect(all).toHaveCount(published([...SUBJECT.core, ...SUBJECT.detail]).length);
    await expect(page.getByRole("button", { name: new RegExp(`^${t.tabSpecs}`) }))
      .toHaveText(new RegExp(`^${t.tabSpecs}\\s*${published([...SUBJECT.core, ...SUBJECT.detail]).length}$`));
    const valued = run(label(index.spec_groups[DETAIL.group ?? ""], locale))
      .filter({ hasText: new RegExp(`^${escape(specLabel(DETAIL.key, locale))}`) });
    await expect(valued.getByRole("cell").nth(1)).toHaveText(new RegExp(`^${quantity(DETAIL)?.value}\\D`));
    await expect(valued.getByRole("cell").nth(1)).not.toContainText(index.spec_definitions[DETAIL.key].unit ?? "");

    await expect(all.locator(".source-chip")).toHaveCount(published([...SUBJECT.core, ...SUBJECT.detail]).length);
    await expect(all.filter({ hasText: t.unknownValue })).toHaveCount(0);

    const unpublished = [...SUBJECT.core, ...SUBJECT.detail].filter((c) => !c.value);
    const fold = page.locator("details.spec-unpublished");
    await expect(fold.locator("summary")).toContainText(String(unpublished.length));
    await expect(fold.locator("li").first()).toBeHidden();
    await fold.locator("summary").focus();
    await page.keyboard.press("Enter");
    await expect(fold.locator("li")).toHaveText(unpublished.map((c) => specLabel(c.key, locale)));
    const shown = await page.locator("main").innerText();
    expect(shown).not.toMatch(SNAKE);
    expect(shown).not.toMatch(/\bunknown\b|\binconnu\b/i);
  });

  test("the rows in no group sit last, under their own heading", async ({ page }) => {
    await page.goto(`/product/${MIXED.slug}`);
    const headings = page.locator("table.spec-table tbody th");
    await expect(headings.last()).toHaveText(t.specGroupOther);
    await expect(headings).toHaveCount(new Set(MIXED.detail.filter((c) => c.value).map((c) => c.group ?? ""))
      .size + (MIXED.core.some((c) => c.value) ? 1 : 0));
  });

  test("the maker's description sits under the specifications, not in the head", async ({ page }) => {
    await page.goto(`/product/${DESCRIBED.slug}`);
    const summary = label(DESCRIPTION, locale);
    const description = page.locator("main section")
      .filter({ has: page.getByRole("heading", { name: t.productDescription, exact: true }) });
    await expect(description.locator("p")).toHaveText(summary);
    expect(await page.locator("table.spec-table").evaluate((table, section) =>
      table.compareDocumentPosition(section) & Node.DOCUMENT_POSITION_FOLLOWING, await description.elementHandle()))
      .toBeTruthy();
    await expect(page.locator("main header")).not.toContainText(summary);
  });

  test("the tab row and the spec table fit their boxes at every width, so neither scrolls", async ({ page }) => {
    await page.goto(`/product/${SUBJECT.slug}`);
    const row = page.getByRole("button", { name: new RegExp(`^${t.tabSpecs}`) }).locator("..");
    const table = page.locator("table.spec-table").first().locator("..");
    for (const width of [375, 768, 1280]) {
      await page.setViewportSize({ width, height: 800 });
      for (const [name, box] of [["tab row", row], ["spec table", table]] as const) {
        expect(await box.evaluate((el) => [el.scrollWidth - el.clientWidth, el.scrollHeight - el.clientHeight]),
          `${name} at ${width} px`).toEqual([0, 0]);
      }
    }
  });
});

test("the prerendered page lists the core rows, then a group's rows under its name, each value with its "
  + "source", async ({ request }) => {
  const html = await (await request.get(`/product/${SUBJECT.slug}`)).text();
  const core = html.indexOf(`>${MESSAGES.en.specSectionCore}</th>`);
  const detail = html.indexOf(`>${label(index.spec_groups[DETAIL.group ?? ""], "en")}</th>`);
  expect(core).toBeGreaterThan(0);
  expect(detail).toBeGreaterThan(core);
  const row = html.slice(detail).split("</tr>").find((r) => r.includes(specLabel(DETAIL.key, "en"))) ?? "";
  expect(row.replace(/<[^>]+>/g, " ")).toContain(String(quantity(DETAIL)?.value));
  expect(row).toContain('class="source-chip');
});

inEachLocale("Product lifecycle", (locale) => {
  const t = MESSAGES[locale];

  test("releases are listed in scheme order with their sources, and licence offerings by type", async ({ page }) => {
    await page.goto(`/product/${RELEASED.slug}`);
    const releases = page.locator("section").filter({ has: page.getByRole("heading", { name: t.versionsTitle }) });
    await expect(releases.locator("tbody tr td:first-child")).toHaveText(RELEASED.versions.map((v) => v.label ?? ""));
    await expect(releases.locator("tbody tr .source-chip")).toHaveCount(RELEASED.versions.length);
    const offerings = page.locator("section").filter({ has: page.getByRole("heading", { name: t.offeringsTitle }) });
    await expect(offerings.locator("tbody tr")).toHaveCount(RELEASED.offerings.length);
    for (const o of RELEASED.offerings) await expect(offerings).toContainText(label(o.licence_type!.label, locale));
  });

  test("a value stated as none shows its reason with its source", async ({ page }) => {
    const [product, key, reason] = ABSENT;
    await page.goto(`/product/${product.slug}`);
    const row = page.locator("table.spec-table tbody tr")
      .filter({ hasText: label(index.spec_definitions[key].label, locale) });
    await expect(row).toContainText(label(reason.label, locale));
    await expect(row.locator(".source-chip")).toHaveCount(1);
  });

  test("a product lists its identifiers under their scheme and its relations under their side's label, a derived one "
    + "so marked", async ({ page }) => {
    for (const v of RELATED) {
      await page.goto(`/product/${v.slug}`);
      for (const i of v.identifiers) await expect(page.locator("dt", { hasText: label(i.scheme.label, locale) })
        .locator("+ dd")).toHaveText(i.value);
      for (const r of v.relations) {
        const group = page.locator('[data-links="relation"]').filter({ hasText: label(r.label, locale) });
        await expect(group.getByRole("link", { name: r.product.name, exact: true })).toBeVisible();
        if (r.basis === "derived") await expect(group).toContainText(t.relationDerived);
      }
    }
  });
});

test("the JSON-LD names an identifier and a related product by the schema.org property their terms "
  + "give", async ({ request }) => {
  for (const [v, properties] of [[MARKED, MARKED.identifiers.flatMap((i) => i.schema_org ?? [])],
    [LINKED, LINKED.relations.flatMap((r) => r.schema_org ?? [])]] as const) {
    const html = await (await request.get(`/product/${v.slug}`)).text();
    for (const property of properties) expect(html, `${v.slug} ${property}`).toContain(`"${property}":`);
  }
});

const STAGED = productViews[0];
const CATEGORY = index.categories.find((c) => c.id === STAGED.category);
const SECOND = index.pipeline_stages.find((s) => !CATEGORY?.pipeline.includes(s.id));
if (!CATEGORY || !SECOND)
  throw new Error("the sample needs a product, its category and a stage that category does not cover");
const STAGES = [...CATEGORY.pipeline, SECOND.id];

inEachLocale("Breadcrumb", (locale) => {
  test("a multi-stage product's breadcrumb links the catalog, its domain and its category, its maker is a link, and "
    + "every stage is a chip", async ({ page }) => {
    await page.route("**/registry.json", async (route) => {
      const response = await route.fetch();
      // Justification (typed boundary): the registry file the build wrote; only its categories' pipelines change.
      const registry = (await response.json()) as { categories: { id: string; pipeline: string[] }[] };
      const categories = registry.categories.map((c) => (c.id === CATEGORY.id ? { ...c, pipeline: STAGES } : c));
      await route.fulfill({ response, json: { ...registry, categories } });
    });
    await page.goto(`/product/${STAGED.slug}`);
    const trail = page.getByRole("navigation", { name: MESSAGES[locale].breadcrumbLabel });
    const links = trail.getByRole("link");
    await expect(links).toHaveText([MESSAGES[locale].catalogTitle, label(index.domains.find((d) =>
      d.id === CATEGORY.domain)?.label ?? { en: "" }, locale), label(CATEGORY.label, locale)]);
    expect(await links.evaluateAll((all) => all.map((a) => a.getAttribute("href"))))
      .toEqual(["/browse", `/browse?domain=${CATEGORY.domain}`, `/category/${CATEGORY.id}`]);
    await expect(page.getByRole("main").getByRole("link", { name: STAGED.vendor.name, exact: true }).first())
      .toHaveAttribute("href", `/vendor/${STAGED.vendor.slug}`);
    const chips = page.locator("[data-stages]");
    await expect(chips).toContainText(MESSAGES[locale].filterByPipeline);
    for (const id of STAGES) await expect(chips)
      .toContainText(label(index.pipeline_stages.find((s) => s.id === id)?.label ?? { en: id }, locale));
    // Justification (typed boundary): the page's one JSON-LD block, a @graph with the Product and its BreadcrumbList.
    const ld = JSON.parse((await page.locator('script[type="application/ld+json"]').textContent())
      ?? "{}") as { "@graph": { "@type": string; itemListElement?: { name: string }[] }[] };
    const crumbs = ld["@graph"].find((n) => n["@type"] === "BreadcrumbList")?.itemListElement?.map((i) => i.name);
    expect(crumbs).toEqual([BRAND_CONFIG.wordmark, label(index.domains.find((d) => d.id === CATEGORY.domain)?.label
      ?? { en: "" }, locale), label(CATEGORY.label, locale), STAGED.name]);
  });
});
