import { test, expect, type APIRequestContext } from "@playwright/test";
import { hostingHeaders } from "../../../scripts/gates/test-hosting.ts";
import { BRAND_CONFIG } from "../../../src/ui/theme/brand.ts";
import { consoleErrors, watchCsp } from "../../fixture.ts";
import { MESSAGES, inEachLocale } from "../../messages.ts";

const GATE = new URL(process.env.SMOKE_BASE_URL ?? "http://127.0.0.1").hostname === "127.0.0.1";
const A_PRODUCT = "a product page";
const A_HUB = "a category hub";
const AN_ARTICLE = "an article";
const A_VENDOR = "a vendor page";
const HEADERS = {
  "strict-transport-security": "max-age=31556926; includeSubDomains; preload",
  "x-content-type-options": "nosniff",
  "x-frame-options": "DENY",
  "referrer-policy": "strict-origin-when-cross-origin",
  "permissions-policy": "camera=(), microphone=(), geolocation=()",
};

const locsOf = async (request: APIRequestContext, url: string): Promise<string[]> =>
  [...(await (await request.get(url)).text()).matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);

async function pagesOf(request: APIRequestContext, kind: string): Promise<string[]> {
  const files =
    await Promise.all((await locsOf(request, "/sitemap.xml")).map((file) => locsOf(request, new URL(file).pathname)));
  return files.flat().map((loc) => new URL(loc).pathname)
    .filter((p) => p.startsWith(`/${kind}/`) && !p.slice(kind.length + 2).includes("/"));
}

async function aPage(request: APIRequestContext, kind: string): Promise<string> {
  const [found] = await pagesOf(request, kind);
  if (!found) throw new Error(`the sitemap lists no ${kind} page`);
  return found;
}

test("sitemap, robots and llms.txt name the canonical https origin", async ({ request }) => {
  const robots = await (await request.get("/robots.txt")).text();
  const origin = robots.match(/^Sitemap: (https:\/\/[^/\s]+)\/sitemap\.xml$/m)?.[1];
  expect(origin, "robots.txt names an https sitemap").toBeDefined();
  const files = await locsOf(request, "/sitemap.xml");
  expect(files.length).toBeGreaterThan(0);
  expect(files.filter((f) => !/\/sitemap-\d+\.xml$/.test(f))).toEqual([]);
  const locs = (await Promise.all(files.map((f) => locsOf(request, new URL(f).pathname)))).flat();
  expect(locs).toContain(`${origin}/`);
  expect(locs).toContain(`${origin}${await aPage(request, "product")}`);
  for (const legal of ["/terms", "/privacy"]) expect(locs).toContain(`${origin}${legal}`);
  expect(locs.filter((loc) => !loc.startsWith(`${origin}/`))).toEqual([]);
  const llms = await (await request.get("/llms.txt")).text();
  const advertised = llms.split(/\s+/).filter((t) => t.startsWith(`${origin}/`) && !t.includes("<"))
    .map((t) => t.slice(origin!.length).replace(/[,.)`]+$/, ""));
  expect(advertised.length).toBeGreaterThan(0);
  for (const path of advertised) expect((await request.get(path)).status(), path).toBe(200);
});

test("the Atom and JSON feeds of the news are served, well formed, and list the published articles", async ({ request,
  page }) => {
  const articles = await pagesOf(request, "news");
  if (GATE) expect(articles.length).toBeGreaterThan(0);
  const latest = articles.slice(0, 50);
  for (const [path, type] of [["/news/feed.atom", "application/atom+xml"],
    ["/news/feed.json", "application/feed+json"]] as const) {
    const response = await request.get(path);
    expect(response.status(), path).toBe(200);
    expect(response.headers()["content-type"], path).toBe(`${type}; charset=utf-8`);
    for (const [key, value] of Object.entries(hostingHeaders(path, GATE)))
      expect(response.headers()[key.toLowerCase()], `${path} ${key}`).toBe(value);
  }
  const feed = await (await request.get("/news/feed.json")).json();
  expect(feed.version).toBe("https://jsonfeed.org/version/1.1");
  expect(feed.items.map((i: { url: string }) => new URL(i.url).pathname)).toEqual(latest);
  await page.goto("/");
  const atom = await page.evaluate(async () => {
    const doc = new DOMParser().parseFromString(await (await fetch("/news/feed.atom")).text(), "application/xml");
    return { error: doc.querySelector("parsererror")?.textContent ?? null, root: doc.documentElement.namespaceURI,
      ids: [...doc.querySelectorAll("entry > id")].map((e) => e.textContent) };
  });
  expect(atom.error).toBeNull();
  expect(atom.root).toBe("http://www.w3.org/2005/Atom");
  expect(atom.ids.map((id) => new URL(id ?? "").pathname)).toEqual(latest);
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

inEachLocale("Smoke", (locale) => {
  test.beforeEach(({ page }) => watchCsp(page));

  const pages = [
    ["/", 200, null], ["/browse", 200, null], [A_PRODUCT, 200, null], [A_HUB, 200, null], [A_VENDOR, 200, null],
    ["/compare", 200, null], ["/news", 200, null], [AN_ARTICLE, 200, null],
    ["/terms", 200, null], ["/privacy", 200, null], ["/product/does-not-exist", 404, "productNotFound"],
    ["/vendor/does-not-exist", 404, "vendorNotFound"], ["/news/does-not-exist", 404, "articleNotFound"],
    ["/no-such-page", 404, "notFoundTitle"],
  ] as const;
  for (const [name, status, notFound] of pages) {
    test(`${name} answers ${status} with the security headers and no CSP violation`, async ({ page, request }) => {
      const errors = consoleErrors(page, /status of 404/);
      const kinds: Record<string, string> = { [A_PRODUCT]: "product", [A_HUB]: "category",
        [A_VENDOR]: "vendor" };
      const path = name === AN_ARTICLE ? (await pagesOf(request, "news"))[0] : kinds[name]
        ? await aPage(request, kinds[name]) : name;
      test.skip(path === undefined, "no article is published yet");
      const response = await page.goto(path);
      expect(response?.status()).toBe(status);
      const headers = response?.headers() ?? {};
      for (const [key, value] of Object.entries(hostingHeaders(path, GATE))) expect(headers[key.toLowerCase()], key)
        .toBe(value);

      await expect(page.locator("html")).toHaveAttribute("lang", locale);
      if (notFound) {
        await expect(page.getByRole("heading", { level: 1 })).toHaveText(MESSAGES[locale][notFound]);
        await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "noindex");
        await expect(page.locator('link[rel="canonical"]')).toHaveCount(0);
        await expect(page.locator('script[type="application/ld+json"]')).toHaveCount(0);
      } else {
        const html = (await response?.text()) ?? "";
        expect(html).toMatch(/<title>[^<]*Machine Vision Radar[^<]*<\/title>/);
        expect(html).toContain('<meta property="og:site_name" content="Machine Vision Radar" />');
        expect(html).toMatch(new RegExp(`<meta name="description" content="[^"]*${BRAND_CONFIG.tagline}`));
        expect(html).toMatch(new RegExp(`<link rel="canonical" href="https://[^/"]+${path === "/" ? "/" : path}" />`));
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      }
      await page.waitForLoadState("networkidle");
      expect(await page.evaluate(() => window.__cspViolations)).toEqual([]);
      expect(errors).toEqual([]);
    });
  }

  test("the admin answers 200 under its own CSP, signed out, noindex and with no violation", async ({ page }) => {
    const errors = consoleErrors(page, /status of 404/);
    for (const path of ["/admin", "/admin/queue"]) {
      const response = await page.goto(path);
      expect(response?.status(), path).toBe(200);
      const headers = response?.headers() ?? {};
      for (const [key, value] of Object.entries(hostingHeaders(path, GATE)))
        expect(headers[key.toLowerCase()], `${path} ${key}`).toBe(value);
      expect(headers["content-security-policy"]).not.toBe(hostingHeaders("/", GATE)["Content-Security-Policy"]);
      await expect(page.getByRole("button", { name: MESSAGES[locale].authSignInButton })).toBeVisible();
      await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "noindex");
      await page.waitForLoadState("networkidle");
      expect(await page.evaluate(() => window.__cspViolations)).toEqual([]);
    }
    await page.route("https://apis.google.com/js/gen_204*",
      (route) => route.fulfill({ status: 302, headers: { location: "https://www.google.com/images/cleardot.gif" } }));
    await page.route("https://www.google.com/**", (route) => route.fulfill({ status: 200, contentType: "image/gif" }));
    expect(await page.evaluate(async () => (await fetch("https://apis.google.com/js/gen_204?c=1", { mode: "no-cors" }))
      .type)).toBe("opaque");
    expect(await page.evaluate(() => window.__cspViolations)).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("the function says what is deployed at /api/health", async ({ request }) => {
    test.skip(GATE, "the hosting emulator runs no function");
    const response = await request.get("/api/health");
    expect(response.status()).toBe(200);
    expect(response.headers()["cache-control"]).toBe("no-store");
    const body = await response.json();
    expect(typeof body.release).toBe("string");
    expect(body.index === null || typeof body.index === "string").toBe(true);
  });

  test("a search runs on the function, with no error", async ({ page, request }) => {
    test.skip(GATE, "the hosting emulator runs no function; search.spec checks /api/find in the gate");
    const errors = consoleErrors(page, /status of 404/);
    await page.goto(await aPage(request, "product"));
    const name = (await page.getByRole("heading", { level: 1 }).textContent()) ?? "";
    await page.goto(`/browse?q=${encodeURIComponent(name)}`);
    await expect(page.getByRole("main").getByRole("article").first()).toBeVisible();
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(MESSAGES[locale].searchErrorTitle)).toHaveCount(0);
    expect(errors).toEqual([]);
  });
});
