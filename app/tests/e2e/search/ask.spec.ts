import { test, expect, type Locator, type Page } from "@playwright/test";
import { MESSAGES, inEachLocale } from "../../messages.ts";
import { index } from "../sample.ts";
import { metrics } from "./metrics.ts";

const QUESTIONS = { en: "glossy widget", fr: "widget brillant" } as const;
const OFF_TOPIC = { en: "What is the capital of Australia?", fr: "Quelle est la capitale de l'Australie ?" } as const;
const PROBLEMS = { en: ["a glossy finish", "zzqxv"], fr: ["une finition brillante", "zzqxv"] } as const;

const answer = (page: Page) => page.locator(".ask-answer");
const cited = (page: Page) => page.getByRole("main").getByRole("listitem").locator("a[href^='/product/']");

inEachLocale("Ask", (locale) => {
  test.beforeEach(async ({ page }, info) => {
    await page.setExtraHTTPHeaders({ "X-Forwarded-For": `198.51.100.${info.workerIndex + 1}${info.title.length}` });
  });

  test("before a question the AI mark, the title and the box sit centred, below the top; an answer moves the box "
    + "up", async ({ page }) => {
    await page.goto("/search");
    const viewport = page.viewportSize();
    if (!viewport) throw new Error("no viewport");
    const box = page.getByRole("textbox", { name: MESSAGES[locale].askTitle });
    const middle = async (locator: Locator) => {
      const b = await locator.boundingBox();
      if (!b) throw new Error("not laid out");
      return { x: b.x + b.width / 2, top: b.y };
    };
    await expect(page.locator("main header svg")).toBeVisible();
    for (const shown of [page.getByRole("heading", { level: 1 }), page.locator("main header svg")])
      expect(Math.abs((await middle(shown)).x - viewport.width / 2)).toBeLessThan(2);
    const before = (await middle(box)).top;
    expect(before).toBeGreaterThan(viewport.height / 4);
    await box.fill(QUESTIONS[locale]);
    await box.press("Enter");
    await expect(page.locator(".ask-answer, .ask-refusal").first()).toBeVisible();
    expect((await middle(box)).top).toBeLessThan(before);
  });

  test("an example question asks itself", async ({ page }) => {
    await page.goto("/search");
    const examples = page.getByRole("list", { name: MESSAGES[locale].askExamplesLabel }).getByRole("button");
    await expect(examples).toHaveCount(3);
    await examples.first().click();
    await expect(page).toHaveURL(/[?&]ask=/);
    await expect(page.locator(".ask-answer, .ask-refusal").first()).toBeVisible();
  });

  test("an answer cites products whose links open their pages, and stays across reload and back", async ({ page }) => {
    await page.goto("/search");
    await page.getByRole("textbox", { name: MESSAGES[locale].askTitle }).fill(QUESTIONS[locale]);
    await page.getByRole("main").getByRole("button", { name: MESSAGES[locale].askAction, exact: true }).click();
    await expect(page)
      .toHaveURL(new RegExp(`ask=${encodeURIComponent(QUESTIONS[locale]).replace(/%20/g, "(%20|\\+)")}`));
    await expect(answer(page)).not.toBeEmpty();
    const links = cited(page);
    await expect(links.first()).toBeVisible();
    const names = await links.allTextContents();
    expect(names.every((n) => index.products.some((p) => p.name === n))).toBe(true);
    const text = await answer(page).textContent();

    await page.reload();
    await expect(answer(page)).toHaveText(text ?? "");

    await page.getByRole("textbox", { name: MESSAGES[locale].askTitle }).fill(OFF_TOPIC[locale]);
    await page.getByRole("main").getByRole("button", { name: MESSAGES[locale].askAction, exact: true }).click();
    await expect(page.locator(".ask-refusal")).toHaveText(MESSAGES[locale].askRefused);
    await page.goBack();
    await expect(answer(page)).toHaveText(text ?? "");

    const first = names[0];
    await links.first().click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(first);
  });

  test("a problem is solved need by need: each need cites the products that meet it, or says none does",
    async ({ page }) => {
      await page.goto(`/search?ask=${encodeURIComponent(PROBLEMS[locale].join("; "))}`);
      const needs = page.getByRole("main").getByRole("listitem")
        .filter({ has: page.getByRole("heading", { level: 3 }) });
      await expect(needs.getByRole("heading", { level: 3 })).toHaveText([...PROBLEMS[locale]]);
      const met = needs.first().getByRole("list", { name: MESSAGES[locale].askCited }).getByRole("link").first();
      await expect(met).toHaveText(index.products.find((p) => p.id === "prd_0000000002")?.name ?? "");
      await expect(needs.nth(1)).toContainText(MESSAGES[locale].askNeedUnmet);
      await met.click();
      await expect(page).toHaveURL(/\/product\//);
    });

  test("past the day's limit a client is told so, and the catalogue's search still works", async ({ page }, info) => {
    const client = `203.0.113.${info.workerIndex + (locale === "en" ? 100 : 150)}`;
    let asked = 0;
    while ((await page.request.post("/api/ask", { headers: { "X-Forwarded-For": client },
      data: { question: `${OFF_TOPIC[locale]} ${asked}`, locale } })).status() === 200) asked++;
    expect(asked).toBeGreaterThan(0);
    await page.setExtraHTTPHeaders({ "X-Forwarded-For": client });
    await page.goto(`/search?ask=${encodeURIComponent(QUESTIONS[locale])}`);
    await expect(page.locator(".ask-refusal")).toHaveText(MESSAGES[locale].askLimit);
    await page.goto(`/browse?q=${encodeURIComponent(index.products[0].name)}`);
    await expect(page.getByRole("main").getByRole("article").first()).toBeVisible();
  });

  test("an endpoint that cannot answer, or cannot be reached, is said to be unavailable", async ({ page }) => {
    const unavailable = { answer: "", citations: [], refused: true, reason: "unavailable" };
    await page.route("**/api/ask",
      (route) => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify(unavailable) }));
    await page.goto(`/search?ask=${encodeURIComponent(QUESTIONS[locale])}`);
    await expect(page.locator(".ask-refusal")).toHaveText(MESSAGES[locale].askUnavailable);
    await page.unroute("**/api/ask");
    await page.route("**/api/ask", (route) => route.abort("connectionrefused"));
    await page.goto(`/search?ask=${encodeURIComponent(OFF_TOPIC[locale])}`);
    await expect(page.getByRole("note")).toHaveText(MESSAGES[locale].askUnavailable);
  });

  test("answers and refusals are counted server-side", async ({ page }) => {
    const before = await metrics();
    await page.goto(`/search?ask=${encodeURIComponent(`${OFF_TOPIC[locale]} (${locale})`)}`);
    await expect(page.locator(".ask-refusal")).toHaveText(MESSAGES[locale].askRefused);
    await expect.poll(async () => (await metrics()).refusal ?? 0).toBeGreaterThan(before.refusal ?? 0);
    await page.goto(`/search?ask=${encodeURIComponent(`${QUESTIONS[locale]} ${locale}`)}`);
    await expect(answer(page)).not.toBeEmpty();
    await expect.poll(async () => (await metrics()).answer ?? 0).toBeGreaterThan(before.answer ?? 0);
  });
});
