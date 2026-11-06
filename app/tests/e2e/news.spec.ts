import { test, expect, type Page } from "@playwright/test";
import { radar } from "../fixture.ts";
import { formatDate } from "../../src/ui/specs/specFormat.ts";
import { MESSAGES, inEachLocale } from "../messages.ts";
import { article, index, label, news } from "./sample.ts";

const titles = (page: Page, level: 2 | 3): Promise<string[]> => page.getByRole("main").getByRole("listitem")
  .getByRole("heading", { level }).allInnerTexts();
const dated = news.items.find((i) => article(i.slug).event_source);
const undated = news.items.find((i) => !article(i.slug).event_date);
const drafted = news.items.find((i) => article(i.slug).authorship === "ai_draft");
const vendor = index.organizations.find((o) => news.items.some((i) => i.subjects.includes(o.id)));
const kind = news.items.find((i) => news.items.some((j) => j.kind.id !== i.kind.id))?.kind;
const category = index.categories.find((c) => c.id === dated?.categories[0]);
if (!dated || !undated || !drafted || !vendor || !kind || !category)
  throw new Error("the fixture's news has no dated article, undated one, AI draft, cited vendor or second kind");
const teaser = index.news.length;

inEachLocale("News", (locale) => {
  const T = MESSAGES[locale];
  const counted = (n: number) => (new Intl.PluralRules(locale).select(n) === "one" ? T.newsCountOne : T.newsCountOther)
    .replace("{count}", String(n));

  test("lists every published article, newest first, as many as `radar feed list` has published", async ({ page }) => {
    // Justification (typed boundary): the JSON `radar feed list` prints; only the published rows are counted.
    const published = (JSON.parse(radar("feed", "list", "--json")) as { published: unknown[] }).published.length;
    await page.goto("/news");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(T.newsTitle);
    await expect(page.getByRole("status")).toHaveText(counted(published));
    expect(await titles(page, 2)).toEqual(news.items.slice(0, 20).map((i) => label(i.title, locale)));
  });

  test("a kind filter is in the address, through a reload and back", async ({ page }) => {
    await page.goto("/news");
    await page.getByRole("group", { name: T.newsFilterLabel })
      .getByRole("button", { name: new RegExp(`^${label(kind.label, locale)}`) }).click();
    const ofKind = news.items.filter((i) => i.kind.id === kind.id);
    await expect(page).toHaveURL(new RegExp(`/news\\?kind=${kind.id}$`));
    await expect(page.getByRole("status")).toHaveText(counted(ofKind.length));
    await page.reload();
    await expect(page.getByRole("status")).toHaveText(counted(ofKind.length));
    expect(await titles(page, 2)).toEqual(ofKind.map((i) => label(i.title, locale)));
    await page.goBack();
    await expect(page).toHaveURL(/\/news$/);
    await expect(page.getByRole("status")).toHaveText(counted(news.total));
  });

  test("an article and its products link both ways, and it dates the vendor's release only with its "
    + "source", async ({ page }) => {
    await page.goto("/news");
    await page.getByRole("link", { name: label(dated.title, locale), exact: true }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(label(dated.title, locale));
    await expect(page.getByRole("term")).toHaveText([T.newsAdded, T.newsVendorRelease]);
    const product = article(dated.slug).body.flatMap((s) => s.cites).find((c) => c.kind === "product");
    if (!product?.label) throw new Error(`${dated.slug} cites no product`);
    await page.getByRole("main").getByRole("link", { name: product.label, exact: true }).first().click();
    await expect(page).toHaveURL(new RegExp(`/product/${product.slug}$`));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(product.label);
    await page.getByRole("main").getByRole("link", { name: label(category.label, locale), exact: true })
      .first().click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(label(category.label, locale));
    await page.getByRole("region", { name: T.newsRecent })
      .getByRole("link", { name: label(dated.title, locale) }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(label(dated.title, locale));

    await page.goto(`/news/${undated.slug}`);
    await expect(page.getByRole("term")).toHaveText([T.newsAdded]);
  });

  test("an AI draft carries its label, dated by the approval that published it, on its page and in both "
    + "feeds", async ({ page, request }) => {
    const said = (code: "en" | "fr") =>
      MESSAGES[code].newsAiDrafted.replace("{date}", formatDate(drafted.published_at, code));
    await page.goto(`/news/${drafted.slug}`);
    await expect(page.getByRole("main").getByText(said(locale))).toBeVisible();
    for (const path of [drafted.slug, "feed.atom", "feed.json"])
      expect((await (await request.get(`/news/${path}`)).text()).split(said("en")), path).toHaveLength(2);
  });

  test("a vendor's page lists its recent articles and opens one", async ({ page }) => {
    await page.goto(`/vendor/${vendor.slug}`);
    const recent = page.getByRole("region", { name: T.newsRecent });
    const about = news.items.filter((i) => i.subjects.includes(vendor.id)).slice(0, 3);
    await expect(recent.getByRole("heading", { level: 3 })).toHaveText(about.map((i) => label(i.title, locale)));
    await recent.getByRole("link", { name: label(about[0].title, locale) }).click();
    await expect(page).toHaveURL(new RegExp(`/news/${about[0].slug}$`));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(label(about[0].title, locale));
    const feed = await (await page.request.get(`/vendor/${vendor.slug}/feed.json`)).json();
    expect(feed.items.map((i: { url: string }) => new URL(i.url).pathname))
      .toEqual(news.items.filter((i) => i.subjects.includes(vendor.id)).map((i) => `/news/${i.slug}`));
  });

  test(`the home shows the latest ${teaser} articles from the registry`, async ({ page }) => {
    await page.goto("/");
    const latest = page.getByRole("region", { name: T.newsLatest });
    await expect(latest.getByRole("heading", { level: 3 }))
      .toHaveText(news.items.slice(0, teaser).map((i) => label(i.title, locale)));
    expect(teaser).toBe(5);
  });
});
