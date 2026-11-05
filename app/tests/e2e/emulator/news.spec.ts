import { randomUUID } from "node:crypto";
import { expect } from "@playwright/test";
import { radar, rows } from "../../fixture.ts";
import { formatPartialDate } from "../../../src/ui/specs/specFormat.ts";
import { inEachLocale, MESSAGES } from "../../messages.ts";
import { decide, founderTest as test, noAxeViolations } from "./admin.ts";

const SOCIAL = /linkedin\.com|twitter\.com|x\.com|facebook\.com|mastodon/;
const [product] = rows<{ id: string }>("products.jsonl");
const [source] = rows<{ id: string }>("sources.jsonl");
const [maker] = rows<{ name: string; slug: string }>("organizations.jsonl");
const draftCalls = rows<{ use: string; day_calls: number }>("ai_caps.jsonl").find((c) => c.use === "draft")?.day_calls;

inEachLocale("the news's desk", (locale) => {
  const T = MESSAGES[locale];

  test("the founder writes, reorders, publishes, shares and retracts two articles", async ({ page }) => {
    test.setTimeout(180_000);
    const run = `${locale}-${randomUUID().slice(0, 8)}`;
    const social: string[] = [];
    page.on("request", (r) => {
      if (SOCIAL.test(new URL(r.url()).hostname)) social.push(r.url());
    });
    await page.goto("/admin/news");
    await expect(page.getByRole("heading", { level: 1, name: T.adminNavNews })).toBeVisible();

    const write = async (title: string, vendorDate = "") => {
      await page.getByRole("button", { name: T.adminNewsWrite }).click();
      await page.getByLabel(T.adminNewsTitleField.replace("{language}", "EN")).fill(title);
      await page.getByLabel(T.adminNewsSummaryField.replace("{language}", "EN")).fill(`What ${title} says.`);
      await page.getByLabel(T.adminNewsSentence.replace("{n}", "1").replace("{language}", "EN"))
        .fill(`${title} rests on a product and a source.`);
      await page.getByLabel(T.adminNewsCitesField.replace("{n}", "1")).fill(`${product.id}, ${source.id}`);
      if (vendorDate) {
        await page.getByLabel(T.adminNewsEventDate).fill(vendorDate);
        await page.getByLabel(T.adminNewsEventSource).fill(source.id);
      }
      await page.getByRole("button", { name: T.adminNewsSave }).click();
      await expect(page.getByRole("heading", { level: 1, name: T.adminNavNews })).toBeVisible();
    };
    const [first, second] = [`First ${run}`, `Second ${run}`];
    await write(first, "2026-06");
    await write(second);
    const drafts = page.getByRole("region", { name: T.adminNewsDrafts }).getByRole("listitem");
    await expect(drafts.filter({ hasText: run })).toHaveText([new RegExp(first), new RegExp(second)]);
    await page.getByRole("button", { name: T.adminNewsUp.replace("{title}", second) }).click();
    await expect(drafts.filter({ hasText: run })).toHaveText([new RegExp(second), new RegExp(first)]);

    const publishNext = async (left: number) => {
      await page.getByLabel(T.adminNote).fill(`Out (${locale})`);
      await page.getByRole("button", { name: T.adminNewsPublishNext }).click();
      await expect(drafts.filter({ hasText: run })).toHaveCount(left);
    };
    await publishNext(1);
    const listedDrafts = JSON.parse(radar("feed", "list", "--json"))
      .drafts as { title: { en: string }; proposal: string }[];
    const [queued] = listedDrafts.filter((d) => d.title.en === first).map((d) => d.proposal);
    expect(queued).toMatch(/^prp_/);
    await page.goto(`/admin/queue/${queued}`);
    await decide(page, T, `Out from the queue (${locale})`);

    await page.goto("/news");
    const listed = page.getByRole("main").getByRole("listitem").getByRole("heading", { level: 2 });
    await expect(listed.filter({ hasText: run })).toHaveText([first, second]);

    await page.goto("/admin/news");
    await page.getByRole("region", { name: T.adminNewsPublished }).getByRole("link", { name: first }).click();
    await expect(page.getByRole("heading", { level: 1, name: first })).toBeVisible();
    await expect(page.getByLabel(T.adminNewsRevisionNote)).toBeVisible();
    const share = page.getByRole("link", { name: T.adminNewsShare.replace("{title}", first) });
    const href = (await share.getAttribute("href")) ?? "";
    const address = decodeURIComponent(href.split("?url=")[1] ?? "");
    expect(href.startsWith("https://www.linkedin.com/sharing/share-offsite/?url=")).toBe(true);
    expect(new URL(address).pathname).toMatch(/^\/news\/first-/);
    await page.getByRole("button", { name: T.adminNewsCopy.replace("{language}", "EN") }).click();
    await expect(page.getByRole("status").filter({ hasText: T.adminNewsCopied })).toBeVisible();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(`${first}\nWhat ${first} says.\n${address}`);
    await page.goto(new URL(address).pathname);
    await expect(page.getByRole("term")).toHaveText([T.newsAdded, T.newsVendorRelease]);
    await expect(page.locator("dd").last())
      .toContainText(formatPartialDate({ value: "2026-06", precision: "month" }, locale));
    await expect(page.locator("dd").last().locator(".source-chip")).toBeVisible();

    const retract = async (title: string) => {
      await page.goto("/admin/news");
      await page.getByRole("region", { name: T.adminNewsPublished }).getByRole("link", { name: title }).click();
      await page.getByLabel(T.adminNewsRetractNote).fill(`Withdrawn (${locale})`);
      await page.getByRole("button", { name: T.adminRetract }).click();
      await expect(page.getByRole("heading", { level: 1, name: T.adminNavNews })).toBeVisible();
    };
    await retract(first);
    await retract(second);
    await page.goto("/news");
    await expect(page.getByRole("status")).toBeVisible();
    await expect(listed.filter({ hasText: run })).toHaveCount(0);
    expect(social).toEqual([]);
    await noAxeViolations(page, ["/admin/news"]);
  });

  test("the founder drafts with AI, is refused at the draft cap with its reason, and publishes the draft "
    + "labelled", async ({ page }) => {
    test.setTimeout(120_000);
    await page.goto("/admin/news");
    const draft = async () => {
      await page.getByLabel(T.adminNewsDraftItem).fill(maker.slug);
      await page.getByRole("button", { name: T.adminNewsDraftWithAi }).click();
    };
    radar("ai-caps", "set", "draft", "--day-calls", "0", "--reason", `No AI draft (${locale})`);
    await draft();
    await expect(page.getByRole("alert")).toContainText("draft: 0 calls a day, made");
    radar("ai-caps", "set", "draft", "--day-calls", String(draftCalls), "--reason", `AI drafts again (${locale})`);
    await draft();
    const listed = page.getByRole("region", { name: T.adminNewsDrafts }).getByRole("listitem");
    await expect(listed).toHaveText([new RegExp(`${maker.name}.*${T.adminNewsAiDraft}`)]);
    await page.getByLabel(T.adminNote).fill(`Reviewed (${locale})`);
    await page.getByRole("button", { name: T.adminNewsPublishNext }).click();
    await expect(listed).toHaveCount(0);
    await page.getByRole("region", { name: T.adminNewsPublished }).getByRole("link", { name: maker.name, exact: true })
      .first().click();
    await page.getByRole("link", { name: /^\/news\// }).click();
    await expect(page.getByText(T.newsAiDrafted.replace("{date}", await page.locator("dd time").innerText())))
      .toBeVisible();
  });
});
