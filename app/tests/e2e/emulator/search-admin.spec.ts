import { expect, type Page } from "@playwright/test";
import type { AiSettings, SearchSettings } from "../../../src/domain/views.ts";
import { registryFile } from "../../fixture.ts";
import { inEachLocale, MESSAGES } from "../../messages.ts";
import { founderTest as test, noAxeViolations } from "./admin.ts";

const SCREENS = ["/admin/search", "/admin/search/console", "/admin/search/settings"];

interface ModelCall { name: string; use: string; model: string; tokens_in: number; tokens_out: number; cad: number }

async function modelCalls(page: Page): Promise<ModelCall[]> {
  const res = await page.request.get(`${process.env.MVR_FIRESTORE_DOCS}/ai_calls?pageSize=1000`,
    { headers: { Authorization: "Bearer owner" } });
  // Justification (typed boundary): the Firestore REST listing; only the fields read here.
  const { documents = [] } = (await res.json()) as { documents?: { name: string; fields: Record<string,
    { stringValue?: string; integerValue?: string; doubleValue?: number }> }[] };
  const field = (doc: (typeof documents)[number], key: string) => doc.fields[key] ?? {};
  return documents.map((d) => ({
    name: d.name, use: field(d, "use").stringValue ?? "", model: field(d, "model").stringValue ?? "",
    tokens_in: Number(field(d, "tokens_in").integerValue), tokens_out: Number(field(d, "tokens_out").integerValue),
    cad: Number(field(d, "cad").doubleValue ?? field(d, "cad").integerValue),
  }));
}

inEachLocale("search management", (locale) => {
  const T = MESSAGES[locale];
  const other = locale === "en" ? "fr" : "en";
  const question = locale === "en" ? "glossy widget" : "widget à finition brillante";

  test("the founder updates the index, tests a question, caps Ask, changes its model and reverts both", async ({ page,
    founder }) => {
    test.setTimeout(150_000);
    const ai = registryFile<AiSettings>("ai.json");
    const search = registryFile<SearchSettings>("search.json");
    const running = ai.models.find((m) => m.id === ai.uses.find((u) => u.use === "ask")?.model);
    const next = ai.models.find((m) => m !== running);
    if (!running || !next) throw new Error("the fixture's ai.json lists two models and Ask's");

    await page.goto("/admin/search");
    await expect(page.getByRole("heading", { level: 1, name: T.adminSearchTitle })).toBeVisible();
    const updated = page.waitForResponse("**/api/admin/search/update", { timeout: 60_000 });
    await page.getByRole("button", { name: T.adminSearchUpdate, exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: T.adminSearchRunning }))
      .toHaveCount(0, { timeout: 60_000 });
    const [newest] = (await (await updated).json()).runs;
    expect([newest.action, newest.actor]).toEqual(["update", founder.email]);
    await expect(page.getByRole("listitem").filter({ hasText: founder.email }).first())
      .toContainText(T.adminSearchUpdate);
    const error = "the index rebuild failed: the model did not load";
    await page.route("**/api/admin/search/rebuild", (route) => route.fulfill({ status: 500, json: { error } }));
    await page.getByRole("button", { name: T.adminSearchRebuild, exact: true }).click();
    await expect(page.getByRole("alert")).toHaveText(T.adminSearchRunFailed.replace("{error}", error));
    await page.unrouteAll();

    const ask = async (question: string) => {
      await page.goto("/admin/search/console");
      await page.getByLabel(T.adminConsoleQuestion).fill(question);
      await page.getByLabel(T.adminConsoleSite).selectOption(other);
      await page.getByRole("main").getByRole("button", { name: T.askAction, exact: true }).click();
      return page.getByRole("region", { name: T.adminConsoleAnswer });
    };
    await expect((await ask(question)).getByRole("list", { name: T.askCited }).getByRole("link").first()).toBeVisible();

    const settings = async () => {
      await page.goto("/admin/search/settings?use=ask");
      return page.getByRole("region", { name: T.adminSettingsAi });
    };
    const uses = await settings();
    await expect(page.getByText(T.adminSettingsEmbedder.split("{model}")[0])).toContainText(search.model);
    await expect(page.getByRole("region", { name: T.adminSettingsSearch }).getByRole("button")).toHaveCount(0);
    await expect(page.getByRole("row", { name: new RegExp(`^${T.adminKnobEvidence}`) }))
      .toContainText(String(search.evidence));
    const askRow = page.getByRole("row", { name: new RegExp(`^${T.adminUseAsk} `) }).getByRole("cell");
    await expect(askRow.first()).toHaveText(running.label);
    await expect(askRow.nth(1)).toHaveText("ask.md");
    const weights = page.getByRole("row", { name: new RegExp(`^${T.adminKnobFields}`) }).getByRole("cell").first();
    await expect(weights)
      .toContainText(`${T.adminSearchFieldVendor} ${search.fields.find((f) => f.field === "vendor")?.weight}`);
    await expect(weights).not.toContainText(new RegExp(`\\b(${search.fields.map((f) => f.field).join("|")})\\b`));
    await page.setViewportSize({ width: 375, height: 812 });
    expect(await page.getByRole("main").innerText()).not.toContain("`");
    expect(await page.evaluate(() => document.documentElement.scrollWidth), "the page scrolls sideways at 375 px")
      .toBeLessThanOrEqual(375);
    const broken = await page.locator("main table .font-mono").evaluateAll((codes) => codes.filter((code) => {
      const range = document.createRange();
      range.selectNodeContents(code);
      return new Set([...range.getClientRects()].map((line) => Math.round(line.top))).size > 1;
    }).map((code) => code.textContent));
    expect(broken, "an id or a command breaks across lines at 375 px").toEqual([]);
    await page.setViewportSize({ width: 1280, height: 720 });

    const change = async (reason: string, set: () => Promise<unknown>) => {
      await set();
      await uses.getByLabel(T.adminReason).fill(reason);
      await uses.getByRole("button", { name: T.adminSettingsSave }).click();
      await expect(page.getByRole("listitem").filter({ hasText: reason })).toBeVisible();
    };
    const revert = async (reason: string) => {
      await settings();
      await uses.getByLabel(T.adminReason).fill(`${reason}: reverted`);
      await page.getByRole("listitem").filter({ hasText: reason })
        .getByRole("button", { name: T.adminCapsRevert }).click();
    };

    await change(`Ask paused (${locale})`, () => uses.getByLabel(T.adminCapsDay).fill("0"));
    await expect(askRow.nth(3))
      .toHaveText(new RegExp(`^${T.adminCapsOf.replace("{used}", "\\d+").replace("{cap}", "0")}$`));
    await expect(await ask(question)).toContainText(T.askLimit);
    await revert(`Ask paused (${locale})`);
    await expect((await ask(question)).getByRole("list", { name: T.askCited })).toBeVisible();

    await settings();
    await change(`Ask on ${next.label} (${locale})`,
      () => uses.getByLabel(T.adminSettingsModel).selectOption({ label: next.label }));
    await expect(askRow.first()).toHaveText(next.label);
    const before = new Set((await modelCalls(page)).map((c) => c.name));
    await expect((await ask(question)).getByRole("list", { name: T.askCited })).toBeVisible();
    const [call, ...more] = (await modelCalls(page)).filter((c) => !before.has(c.name));
    expect([call?.use, call?.model, more.length], "one call, the scripted model answering as the model chosen")
      .toEqual(["ask", next.id, 0]);
    expect(call.cad)
      .toBeCloseTo(((call.tokens_in * next.usd_in + call.tokens_out * next.usd_out) * ai.cad_per_usd) / 1e6, 8);
    await revert(`Ask on ${next.label} (${locale})`);
    await expect(askRow.first()).toHaveText(running.label);

    await noAxeViolations(page, SCREENS);
  });
});
