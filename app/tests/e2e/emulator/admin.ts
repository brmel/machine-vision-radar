import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DEV } from "../../../scripts/head.ts";
import AxeBuilder from "@axe-core/playwright";
import { test as base, expect, type BrowserContext, type Page } from "@playwright/test";
import { radar } from "../../fixture.ts";
import { inLocale, MESSAGES } from "../../messages.ts";

type Messages = (typeof MESSAGES)[keyof typeof MESSAGES];
type Founder = { email: string; session: Awaited<ReturnType<BrowserContext["storageState"]>> };

const MODEL: { id: string; label?: Record<string, string>; fields: Record<string,
  { label?: Record<string, string>; optional?: boolean }> }[] =
  JSON.parse(readFileSync(join(DEV, "contracts", "model", "entities.json"), "utf8"));

const fieldOf = (entity: string, field: string) => MODEL.find((e) => e.id === entity)?.fields[field];

export function fieldLabel(entity: string, field: string, locale: string): string {
  const spec = fieldOf(entity, field);
  return `${spec?.label?.[locale]}${spec?.optional ? "" : " *"}`;
}

export const kindLabel = (entity: string, locale: string): string =>
  MODEL.find((e) => e.id === entity)?.label?.[locale] ?? "";

export const addLabel = (T: Messages, entity: string, field: string, locale: string): string =>
  T.adminAdd.replace("{kind}", kindLabel(entity, locale))
    .replace("{field}", fieldOf(entity, field)?.label?.[locale] ?? "");

export async function modelKeysShown(page: Page): Promise<string[]> {
  const names = new Set(MODEL.flatMap((e) => Object.keys(e.fields)));
  const labels = await page.locator("main label, main legend").allInnerTexts();
  return labels.map((text) => text.split("\n")[0].replace(/ \*$/, "")).filter((text) => names.has(text));
}

export const test = base.extend<object, { founder: Founder }>({
  founder: [async ({ browser }, use, { project }) => {
    const email = `founder-${randomUUID().slice(0, 8)}@example.com`;
    const idp =
      new URLSearchParams({ providerId: "google.com", id_token: JSON.stringify({ sub: randomUUID(), email }) });
    const auth = `http://${process.env.FIREBASE_AUTH_EMULATOR_HOST}/identitytoolkit.googleapis.com/v1`;
    const res = await fetch(`${auth}/accounts:signInWithIdp?key=${process.env.VITE_FIREBASE_API_KEY}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ requestUri: "http://localhost", postBody: idp.toString() }),
    });
    expect(res.status, await res.text()).toBe(200);
    radar("admin", "grant", email);
    const context = await browser.newContext({ baseURL: project.use.baseURL });
    await inLocale(context, "en");
    const page = await context.newPage();
    await page.goto("/admin");
    await signIn(page, email, MESSAGES.en.authSignInButton, false);
    await expect(page.getByRole("heading", { level: 1, name: MESSAGES.en.adminQueueTitle })).toBeVisible();
    const session = await context.storageState({ indexedDB: true });
    await context.close();
    await use({ email, session });
  }, { scope: "worker" }],
});

export const founderTest = test.extend({ storageState: ({ founder }, use) => use(founder.session) });

async function signIn(page: Page, email: string, button: string, fresh: boolean): Promise<void> {
  const [popup] = await Promise.all([page.waitForEvent("popup"), page.getByRole("button", { name: button }).click()]);
  await popup.waitForLoadState();
  if (fresh) {
    await popup.getByText("Add new account").click();
    await popup.locator("#email-input").fill(email);
    await popup.getByRole("button", { name: /Sign in with Google.com/i }).click();
  } else {
    await popup.getByText(email).click();
  }
}

export async function asFounder(page: Page, T: Messages, email: string): Promise<void> {
  await page.goto("/admin");
  await expect(page.getByRole("button", { name: T.authSignInButton })).toBeVisible();
  await signIn(page, email, T.authSignInButton, true);
  await expect(page.getByRole("heading", { level: 1, name: T.authDeniedTitle })).toBeVisible();
  radar("admin", "grant", email);
  await page.getByRole("button", { name: T.authSignOut }).click();
  await signIn(page, email, T.authSignInButton, false);
}

export async function decide(page: Page, T: Messages, note: string, action = T.adminApprove,
    status = T.adminStatusApproved): Promise<void> {
  await page.getByLabel(T.adminNote).fill(note);
  await page.getByRole("button", { name: action, exact: true }).click();
  await expect(page.locator("article header p").first()).toHaveText(new RegExp(`^${status} ·`), { timeout: 60_000 });
}

export async function citeNewSource(page: Page, T: Messages, url: string): Promise<void> {
  await page.getByLabel(`${T.adminSourceType} *`).selectOption({ index: 1 });
  await page.getByLabel(T.adminSourceUrl, { exact: true }).fill(url);
}

export async function fileApproved(page: Page, T: Messages, reason: string): Promise<string> {
  await page.getByLabel(`${T.adminReason} *`).fill(reason);
  await page.getByRole("button", { name: T.adminFile }).click();
  await decide(page, T, `Checked: ${reason}`);
  return (await page.locator("a[href^='/admin/records/']").first().textContent()) ?? "";
}

export async function noAxeViolations(page: Page, paths: readonly string[]): Promise<void> {
  for (const theme of ["light", "dark"] as const) {
    await page.evaluate((t) => localStorage.setItem("machineVisionRadar.themePreference", t), theme);
    for (const path of paths) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await page.waitForLoadState("networkidle");
      const { violations } = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
      expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical")
        .map((v) => `${theme} ${path}: ${v.id}`)).toEqual([]);
    }
  }
}
