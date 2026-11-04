import { test, expect } from "@playwright/test";
import { watchCsp } from "../../fixture.ts";
import { PAGES } from "../sample.ts";

const NOT_FOUND = /Page not found|Page introuvable|404/i;
const HEADERS = {
  "strict-transport-security": "max-age=31556926; includeSubDomains; preload",
  "x-content-type-options": "nosniff",
  "x-frame-options": "DENY",
  "referrer-policy": "strict-origin-when-cross-origin",
  "permissions-policy": "camera=(), microphone=(), geolocation=()",
};

test("the public pages, semantic search, FR, a 404 and the admin's sign-in run with no CSP violation or console "
  + "error", async ({ page }) => {
  test.setTimeout(90_000);
  const errors: string[] = [];
  let notFound = false;
  page.on("console", (msg) => {
    if (msg.type() === "error" && !(notFound && /404|Failed to load resource/.test(msg.text())))
      errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  await watchCsp(page);
  const clean = async (stage: string) => {
    expect(await page.evaluate(() => window.__cspViolations), stage).toEqual([]);
    expect(errors, stage).toEqual([]);
  };

  for (const [path, ready] of [["/", "main h1"], ["/browse", "main article"], [PAGES.product, "main h1"],
    [PAGES.vendor, "main h1"], ["/compare", "main"]]) {
    await page.goto(path);
    await expect(page.locator(ready).first()).toBeVisible();
    await clean(path);
  }

  await page.goto(`/browse?q=${encodeURIComponent("a shiny polished gadget")}`);
  await expect(page.locator("main").getByRole("article").first()).toBeVisible({ timeout: 60_000 });
  await clean("search by meaning");
  await page.getByRole("button", { name: "FR", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "fr");
  await clean("FR");

  await page.goto("/admin");
  await expect(page.getByRole("button", { name: /Sign in with Google|Se connecter avec Google/ })).toBeVisible();
  await page.route("https://apis.google.com/js/gen_204*",
    (route) => route.fulfill({ status: 302, headers: { location: "https://www.google.com/images/cleardot.gif" } }));
  await page.route("https://www.google.com/**", (route) => route.fulfill({ status: 200, contentType: "image/gif" }));
  expect(await page.evaluate(async () => (await fetch("https://apis.google.com/js/gen_204?c=1", { mode: "no-cors" }))
    .type)).toBe("opaque");
  await clean("admin sign-in");

  notFound = true;
  await page.goto("/administrator");
  await expect(page.locator("main")).toContainText(NOT_FOUND);
  await clean("a look-alike of the admin's address");
});

test("the site is served with HSTS, the security headers and a CSP without eval or a CDN", async ({ request }) => {
  const res = await request.get("/");
  expect(res.status()).toBe(200);
  const headers = res.headers();
  for (const [key, value] of Object.entries(HEADERS)) expect(headers[key], key).toBe(value);
  const csp = headers["content-security-policy"];
  expect(csp).toContain("default-src 'self'");
  expect(csp).toContain("script-src 'self' ");
  for (const banned of ["preload", "jsdelivr", "unsafe-eval", "huggingface", "worker-src"])
    expect(csp).not.toContain(banned);
});
