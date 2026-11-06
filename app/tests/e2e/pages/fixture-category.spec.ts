import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DEV } from "../../../scripts/head.ts";
import { test, expect, type Page } from "@playwright/test";
import { registryFile, rows as fixtureRows } from "../../fixture.ts";
import { MESSAGES, inEachLocale } from "../../messages.ts";

type Text = { en: string; fr: string };
interface Term { id: string; label: Text; description: Text }
interface Fixture {
  registry: {
    "categories.json": Term[];
    "vocabularies/domains.json": Term[];
    "spec_definitions.json": (Term & { unit?: string; precision?: number })[];
  };
}
interface Rows {
  "products.jsonl": { id: string; slug: string; version: number; parent?: string };
  "names.jsonl": { subject: string; value: string; is_primary: boolean };
  "claims.jsonl": { subject: string; spec_key: string;
    value: { quantity?: { value: number; unit: string }; term?: string } };
  "documents.jsonl": { kind: string; source_url: string; title: Text; rights: string; subjects: string[] };
  "changes.jsonl": { entity: string; recorded_at: string; reason: string; patch: { path: string; value?: string }[] };
}

// Justification (typed boundary): the fixture file the Python builder reads; only the fields above are used.
const fixture = JSON.parse(readFileSync(join(DEV, "radar/tests/fixtures/fixture_category.json"), "utf8")) as Fixture;
const rows = <K extends keyof Rows>(name: K): Rows[K][] => fixtureRows<Rows[K]>(name);

const [category] = fixture.registry["categories.json"];
const [domain] = fixture.registry["vocabularies/domains.json"];
const [reach, finish] = fixture.registry["spec_definitions.json"];
const products = rows("products.jsonl");
const family = products.find((p) => products.some((m) => m.parent === p.id))!;
const models = products.filter((p) => p.parent === family.id);
const versioned = products.find((p) => p.version > 1)!;
const states = registryFile<Term[]>("vocabularies/lifecycle_event_states.json");
const planned = states.find((s) => s.id === "planned")!.label;
const rights = registryFile<{ id: string; public?: boolean }[]>("vocabularies/media_rights.json");
const factors = new Map(registryFile<{ id: string; factor: number }[]>("units.json").map((u) => [u.id, u.factor]));
const restated = rows("claims.jsonl")
  .find((c) => c.spec_key === reach.id && c.value.quantity && c.value.quantity.unit !== reach.unit)!;
const converted =
  Number(((restated.value.quantity!.value * factors.get(restated.value.quantity!.unit)!) / factors.get(reach.unit!)!)
    .toPrecision(12));
const restatedAs = reach.precision === undefined ? converted : Number(converted.toFixed(reach.precision));
const nameOf = (id: string) => rows("names.jsonl").find((n) => n.subject === id && n.is_primary)?.value ?? id;
const KINDS = { en: ["Datasheet", "Image"], fr: ["Fiche technique", "Image"] } as const;
const FILES = { en: ["PDF · 62 bytes", "PNG · 2 kB"], fr: ["PDF · 62 octets", "PNG · 2 ko"] } as const;
const NOTES = { en: "TEXT · 60 bytes", fr: "TEXT · 60 octets" } as const;

inEachLocale("A category added only to the registry", (locale) => {
  const t = MESSAGES[locale];
  const reachRow = `${reach.label[locale]} (${reach.unit})`;
  const row = (page: Page, text: string) =>
    page.getByRole("row", { name: new RegExp(`^${text.replace(/[()]/g, "\\$&")}`) });

  test("a reach stated in another unit shows and filters in its spec's unit", async ({ page }) => {
    const product = products.find((p) => p.id === restated.subject)!;
    await page.goto(`/product/${product.slug}`);
    await expect(row(page, reachRow)).toContainText(new Intl.NumberFormat(locale).format(restatedAs));
    await page.goto(`/browse?category=${category.id}&${reach.id}_min=${restatedAs}&${reach.id}_max=${restatedAs}`);
    await expect(page.getByRole("main").getByRole("article").getByRole("link", { name: nameOf(product.id) }))
      .toBeVisible();
  });

  test("a family lists its models, its range and its media by kind, and has no History; a model links back, no "
    + "range", async ({ page, request }) => {
    await page.goto(`/product/${family.slug}`);
    await expect(page.getByRole("link", { name: t.historyLink })).toHaveCount(0);
    const media = page.locator("section.media");
    await expect(media.getByRole("heading", { name: t.mediaTitle })).toBeVisible();
    await expect(media.locator("h3")).toHaveText(KINDS[locale]);
    await expect(media.getByRole("listitem")).toContainText(FILES[locale]);
    for (const doc of rows("documents.jsonl").filter((d) => d.subjects.includes(family.id))) {
      const link = media.getByRole("link", { name: doc.title[locale] });
      if (rights.find((r) => r.id === doc.rights)?.public) {
        await expect(link).toHaveAttribute("href", /^https?:\/\/[^/]+\/v0\/b\/[^/]+\/o\/media%2F/);
        const file = await request.get((await link.getAttribute("href")) ?? "");
        expect([file.status(), file.headers()["content-type"]]).toEqual([200, expect.stringContaining("image/png")]);
      } else await expect(link).toHaveAttribute("href", doc.source_url);
    }
    await expect(media.locator('a[href*="blobs"]')).toHaveCount(0);
    await expect(page.getByRole("navigation", { name: t.breadcrumbLabel })).toContainText(domain.label[locale]);
    await expect(row(page, reachRow).first()).toContainText("–");
    const modelLinks = page.locator("section.models table").getByRole("link");
    await expect(modelLinks).toHaveText(models.map((m) => nameOf(m.id)).sort());
    await expect(page.locator("section.models")).toContainText(t.unknownValue);
    await modelLinks.first().click();
    await expect(page.getByRole("heading", { level: 1 }))
      .toHaveText(nameOf(models.map((m) => m.id).sort((a, b) => nameOf(a).localeCompare(nameOf(b)))[0]));
    await expect(page.locator('[data-links="family"]')).toContainText(t.familyLink);
    await page.locator('[data-links="family"]').getByRole("link").click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(nameOf(family.id));
  });

  test("a planned event is marked planned; History lists every version, newest first", async ({ page }) => {
    await page.goto(`/product/${versioned.slug}`);
    await expect(page.locator('.lifecycle li[data-state="planned"]').locator(".lifecycle-state"))
      .toHaveText(planned[locale]);
    const media = page.locator("section.media");
    await expect(media.getByRole("heading", { name: t.mediaTitle })).toBeVisible();
    for (const doc of rows("documents.jsonl")
      .filter((d) => d.subjects.some((s) => s === versioned.id || s.startsWith("ver_")))) {
      const link = media.getByRole("link", { name: doc.title[locale] });
      if (rights.find((r) => r.id === doc.rights)?.public) {
        await expect(link).toHaveAttribute("href", /^https?:\/\/[^/]+\/v0\/b\/[^/]+\/o\/media%2F/);
        if (doc.source_url) await expect(media.locator(`a[href="${doc.source_url}"]`)).toHaveText(t.mediaSource);
      } else await expect(link).toHaveAttribute("href", doc.source_url);
    }
    await expect(media).toContainText("(1.2.0)");
    await expect(media).toContainText(NOTES[locale]);
    await page.getByRole("link", { name: t.historyLink }).click();
    await expect(page).toHaveURL(new RegExp(`/product/${versioned.slug}/history$`));
    const versions = page.locator("ol.history > li");
    const named = rows("changes.jsonl")
      .filter((c) => c.patch.some((p) => p.path === "subject" && p.value === JSON.stringify(versioned.id)));
    const specs =
      new Map(named.map((c) => [c.entity, JSON.parse(c.patch.find((p) => p.path === "spec_key")!.value!) as string]));
    const changes = rows("changes.jsonl").filter((c) => c.entity === versioned.id || specs.has(c.entity))
      .sort((a, b) => b.recorded_at.localeCompare(a.recorded_at));
    await expect(versions).toHaveCount(changes.length);
    for (const [i, c] of changes.entries()) {
      await expect(versions.nth(i)).toContainText(c.reason);
      if (specs.has(c.entity)) await expect(versions.nth(i).locator("p").first()).toContainText(specs.get(c.entity)!);
    }
    await expect(versions.first().locator(".source-chip")).toHaveCount(1);
  });

  test("compare shows the products on its specs, with Not published where a model has no value", async ({ page }) => {
    const ids = [models[0].id, models[1].id];
    await page.goto(`/compare?ids=${ids.join(",")}`);
    for (const id of ids) await expect(page.getByRole("columnheader", { name: nameOf(id) })).toBeVisible();
    await expect(row(page, reachRow).getByRole("cell")).toHaveCount(ids.length);
    const finishCells = row(page, finish.label[locale]).getByRole("cell");
    await expect(finishCells).toHaveCount(ids.length);
    await expect(finishCells.filter({ hasText: t.unknownValue })).toHaveCount(ids.filter((id) => !rows("claims.jsonl")
      .some((c) => c.subject === id && c.spec_key === finish.id)).length);
  });
});
