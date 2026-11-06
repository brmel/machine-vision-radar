import { test, expect, type Page } from "@playwright/test";
import { radar } from "../../fixture.ts";
import { escape, index, label, productViews } from "../sample.ts";
import { MESSAGES, inEachLocale } from "../../messages.ts";

const hubbed = index.categories.filter((c) => c.products > 0);
const category = hubbed[0];
const components = productViews.filter((v) => v.hub);
const component = components[0];
if (!component?.hub) throw new Error("no fixture product other products use: the fixture's relations name one");
const hub = `/${component.hub.path}/${component.slug}`;
const users = productViews.filter((v) => v.components.some((c) => c.id === component.id));
interface Listed { products?: number; users?: number; cards: { name: string }[] }
function radarJson(...args: string[]): Listed {
  // Justification (typed boundary): the JSON `radar category show` and `radar hub show` print; only these fields are
  return JSON.parse(radar(...args, "--json")) as Listed;
}

const listed = (page: Page): Promise<string[]> => page.getByRole("main").getByRole("article").getByRole("heading")
  .allInnerTexts();

inEachLocale("Category hubs", (locale) => {
  test("a hub shows its name, description and count, and it and its products link both ways", async ({ page }) => {
    await page.goto(`/category/${category.id}`);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(label(category.label, locale));
    await expect(page.getByRole("main")).toContainText(label(category.description, locale));
    await expect(page.getByRole("status").first()).toHaveText(new RegExp(`^${category.products} `));
    const first = page.getByRole("main").getByRole("article").first().getByRole("heading").getByRole("link");
    const name = (await first.textContent()) ?? "";
    await first.click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(name);
    await page.getByRole("main").getByRole("link", { name: label(category.label, locale), exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/category/${escape(category.id)}$`));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(label(category.label, locale));
  });

  test("a component's hub lists the products that use it, and links both ways with them and with "
    + "it", async ({ page }) => {
    const count = component.hub?.users ?? 0;
    await page.goto(hub);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(component.name);
    await expect(page.getByRole("status")).toContainText(String(count));
    await expect(page.getByRole("main").getByRole("article")).toHaveCount(count);
    await page.getByRole("main").getByRole("link", { name: users[0].name, exact: true }).first().click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(users[0].name);
    await page.locator("[data-links=components]").getByRole("link", { name: component.name, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${escape(hub)}$`));
    await page.goto(`/product/${component.slug}`);
    await page.locator("[data-links=hub]")
      .getByRole("link", { name: MESSAGES[locale].usedByOther.replace("{count}", String(count)) }).click();
    await expect(page).toHaveURL(new RegExp(`${escape(hub)}$`));
  });

  test("a two-part address no category names as its hubs' path is the site's not-found page", async ({ page }) => {
    await page.goto(`/not-a-hub/${component.slug}`);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(MESSAGES[locale].notFoundTitle);
  });

  test("a browse address that names a category lands on its hub, filters kept", async ({ page }) => {
    await page.goto(`/browse?category=${category.id}&sort=vendor`);
    await expect(page).toHaveURL(new RegExp(`/category/${escape(category.id)}\\?sort=vendor$`));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(label(category.label, locale));
  });
});

test("radar category show and radar hub show list the products and counts the hubs list", async ({ page }) => {
  const shown = radarJson("category", "show", category.id);
  await page.goto(`/category/${category.id}`);
  await expect(page.getByRole("status").first()).toHaveText(new RegExp(`^${shown.products} `));
  expect(await listed(page)).toEqual(shown.cards.slice(0, 20).map((c) => c.name));
  const used = radarJson("hub", "show", component.hub?.path ?? "", component.slug);
  await page.goto(hub);
  await expect(page.getByRole("main").getByRole("article")).toHaveCount(used.users ?? 0);
  expect(await listed(page)).toEqual(used.cards.map((c) => c.name));
});

test("a thin product page is noindex and out of the sitemap, and the noindex leaves with it", async ({ page,
  request }) => {
  const thin = productViews.filter((v) => !v.indexable);
  expect(thin.length).toBeGreaterThan(0);
  const sitemap = await (await request.get("/sitemap-1.xml")).text();
  for (const v of productViews) {
    const html = await (await request.get(`/product/${v.slug}`)).text();
    expect(html.includes('<meta name="robots" content="noindex" />'), v.slug).toBe(!v.indexable);
    if (!v.indexable) expect(sitemap.includes(`/product/${v.slug}/history</loc>`), v.slug).toBe(false);
  }
  await page.goto(`/product/${thin[0].slug}`);
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "noindex");
  await page.getByRole("main").getByRole("link", { name: label(category.label, "en"), exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(label(category.label, "en"));
  await expect(page.locator('meta[name="robots"]')).toHaveCount(0);
});

test("every hub is prerendered with its JSON-LD and listed in the sitemap with a date", async ({ request }) => {
  const sitemap = await (await request.get("/sitemap-1.xml")).text();
  for (const c of hubbed) {
    const html = await (await request.get(`/category/${c.id}`)).text();
    expect(html, c.id).toContain(`>${label(c.label, "en")}</h1>`);
    expect(html, c.id).toContain('"@type":"ItemList"');
    expect(html, c.id).toContain('"@type":"BreadcrumbList"');
    expect(html, c.id).toMatch(new RegExp(`<link rel="alternate" type="application/atom\\+xml" href="[^"]+/category/`
      + `${escape(c.id)}/feed\\.atom" />`));
    const feed = await request.get(`/category/${c.id}/feed.atom`);
    expect(feed.status(), c.id).toBe(200);
    expect(feed.headers()["content-type"], c.id).toContain("application/atom+xml");
    expect(sitemap, c.id)
      .toMatch(new RegExp(`/category/${escape(c.id)}</loc>\\s*<lastmod>\\d{4}-\\d{2}-\\d{2}</lastmod>`));
  }
  for (const v of components) {
    const at = `/${v.hub?.path}/${v.slug}`;
    const html = await (await request.get(at)).text();
    expect(html, at).toContain(`>${v.name}</h1>`);
    expect(html, at).toContain('"@type":"ItemList"');
    expect(sitemap, at).toMatch(new RegExp(`${escape(at)}</loc>\\s*<lastmod>\\d{4}-\\d{2}-\\d{2}</lastmod>`));
  }
});

test("once the app has rendered, a hub, a product page and a component's hub each carry one JSON-LD block, their "
  + "own", async ({ page }) => {
  const jsonLd = page.locator('script[type="application/ld+json"]');
  const graph = () => expect.poll(() => jsonLd.textContent());
  await page.goto(`/category/${category.id}`);
  await expect(page.getByRole("main").getByRole("article").first()).toBeVisible();
  await expect(jsonLd).toHaveCount(1);
  await graph().toContain('"@type":"ItemList"');
  await page.getByRole("main").getByRole("article").first().getByRole("heading").getByRole("link").click();
  await expect(jsonLd).toHaveCount(1);
  await graph().toContain('"@type":"Product"');
  await page.goto(hub);
  await expect(page.getByRole("main").getByRole("article").first()).toBeVisible();
  await expect(jsonLd).toHaveCount(1);
  await graph().toContain(`"name":${JSON.stringify(component.name)}`);
});
