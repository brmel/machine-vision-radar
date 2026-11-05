import { test, expect } from "@playwright/test";
import { MESSAGES, inEachLocale } from "../../messages.ts";
import { PAGES, index, escape, label, quietTest, word } from "../sample.ts";

test.describe("Critical paths", () => {
  quietTest("theme toggle, in the header and on the system's theme first, switches light/dark CSS and persists across "
    + "reload", async ({ page }) => {
    await page.goto("/");
    const toggle = page.getByRole("banner").getByRole("group", { name: MESSAGES.en.themeToggle });
    const darkBtn = toggle.getByRole("button", { name: "Dark", exact: true });
    const lightBtn = toggle.getByRole("button", { name: "Light", exact: true });
    const canvas = page.locator("#root > div");
    await expect(page.getByRole("contentinfo").getByRole("group", { name: MESSAGES.en.themeToggle })).toHaveCount(0);
    await expect(toggle.getByRole("button", { name: MESSAGES.en.themeSystem, exact: true }))
      .toHaveAttribute("aria-pressed", "true");

    await darkBtn.click();
    await expect(page.locator("html")).toHaveClass(/dark/);
    await expect(darkBtn).toHaveAttribute("aria-pressed", "true");
    await expect(canvas).toHaveCSS("background-color", "rgb(9, 13, 20)");

    await page.reload();
    await expect(page.locator("html")).toHaveClass(/dark/);
    await expect(darkBtn).toHaveAttribute("aria-pressed", "true");

    await lightBtn.click();
    await expect(page.locator("html")).not.toHaveClass(/dark/);
    await expect(lightBtn).toHaveAttribute("aria-pressed", "true");
    await expect(canvas).toHaveCSS("background-color", "rgb(248, 250, 252)");
  });

  quietTest("product card click navigates to product detail and its breadcrumb back to the "
    + "catalog", async ({ page }) => {
    await page.goto("/browse");
    const firstLink = page.locator("main").getByRole("article").first().getByRole("heading").getByRole("link");
    const firstTitle = (await firstLink.textContent())?.trim() ?? "";
    expect(firstTitle.length).toBeGreaterThan(0);

    await firstLink.click();
    await expect(page).toHaveURL(/\/product\/[a-z0-9-]+__[a-z0-9-]+$/);
    await expect(page.locator("main h1")).toHaveText(firstTitle);

    await page.getByRole("navigation", { name: "Breadcrumb" })
      .getByRole("link", { name: "Catalog", exact: true }).click();
    await expect(page).toHaveURL(/\/browse$/);
    const home = page.getByRole("banner").getByRole("link", { name: "Machine Vision Radar" });
    await expect(home).toHaveAttribute("href", "/");
    await home.click();
    await expect(page).toHaveURL(/\/$/);
  });

  quietTest("compare add, capacity cap, reload persistence, remove, and clear", async ({ page }) => {
    await page.goto("/browse");
    const compareButtons = page.locator("main").getByRole("button", { name: "Compare", exact: true });
    await expect(compareButtons.first()).toBeVisible();

    for (let n = 0; n < 3; n++) await compareButtons.nth(0).click();

    await expect(page.getByText("3/3 selected")).toBeVisible();
    await expect(compareButtons.first()).toBeDisabled();

    await page.getByRole("button", { name: "Compare", exact: true }).last().click();
    await expect(page).toHaveURL(/\/compare\?ids=/);
    await expect(page.locator("table thead th")).toHaveCount(4);

    await page.reload();
    await expect(page.locator("table thead th")).toHaveCount(4);

    await page.getByRole("button", { name: "Remove product from comparison" }).first().click();
    await expect(page.locator("table thead th")).toHaveCount(3);

    await page.getByRole("button", { name: "Remove all" }).click();
    await expect(page.getByText("Pick up to 3 products in the catalog to compare them.")).toBeVisible();
  });

  quietTest("the compare tray keeps the footer clear at the page's end", async ({ page }) => {
    await page.goto("/browse");
    await page.getByRole("main").getByRole("button", { name: MESSAGES.en.compareAction, exact: true }).first().click();
    const tray = page.getByRole("button", { name: MESSAGES.en.compareAction, exact: true }).last();
    await expect(tray).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    const footer = await page.getByRole("contentinfo").boundingBox();
    const trayBox = await page.locator("div.fixed").filter({ has: tray }).boundingBox();
    expect(footer && trayBox && footer.y + footer.height <= trayBox.y).toBe(true);
  });

  quietTest("a pipeline stage from home", async ({ page }) => {
    await page.goto("/");
    const stage =
      index.pipeline_stages.find((s) => index.categories.some((c) => c.products > 0 && c.pipeline.includes(s.id)));
    if (!stage) throw new Error("no pipeline stage with a category that has products");
    await page.getByRole("main").getByRole("link", { name: label(stage.label, "en") }).first().click();
    await expect(page).toHaveURL(new RegExp(`/browse\\?stage=${escape(stage.id)}$`));
    await expect(page.getByRole("status")).toHaveText(/^\d+ products$/);
  });

  quietTest("the admin loads only at /admin, behind a sign-in, and no public page fetches its code or links "
    + "it", async ({ page }) => {
    const admin: string[] = [];
    page.on("request", (r) => {
      if (/\/assets\/AdminSection-[^/]+\.js$/.test(r.url())) admin.push(r.url());
    });
    for (const path of ["/", PAGES.browse, PAGES.product]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await expect(page.locator("header").getByRole("button", { name: /^admin$/i })).toHaveCount(0);
    }
    expect(admin).toEqual([]);
    await page.goto("/admin");
    await expect(page.getByRole("button", { name: "Sign in with Google" })).toBeVisible();
    expect(admin).toHaveLength(1);
  });
});

inEachLocale("Navigation", (locale) => {
  test("the menu has one entry per place, and compare is reached from the products picked", async ({ page }) => {
    await page.goto("/");
    const m = MESSAGES[locale];
    const menu = page.getByRole("banner").getByRole("navigation").first();
    await expect(menu.getByRole("link")).toHaveText([m.navHome, m.navBrowse, m.navAsk, m.newsTitle, m.navAbout]);
    await expect(page.getByRole("banner").getByRole("link", { name: m.navBrowse })).toHaveCount(1);

    await page.getByRole("main").getByRole("textbox").first().fill(word);
    await page.getByRole("main").getByRole("textbox").first().press("Enter");
    await expect(page).toHaveURL(new RegExp(`/browse\\?q=${escape(encodeURIComponent(word))}`));
    await expect(page.getByRole("main").getByRole("textbox").first()).toHaveValue(word);

    await page.getByRole("main").getByRole("button", { name: m.compareAction, exact: true }).first().click();
    await page.goto("/admin");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: m.compareAction, exact: true })).toHaveCount(0);
    await page.goBack();
    await page.getByRole("button", { name: m.compareAction, exact: true }).last().click();
    await expect(page).toHaveURL(/\/compare\?ids=/);
  });
});

inEachLocale("The vision pipeline", (locale) => {
  test("the home shows each stage in order, one card each, of one height, with what it holds and its products; then "
    + "each domain, a card each; every card a link", async ({ page }) => {
    await page.goto("/");
    const section = page.getByRole("region", { name: MESSAGES[locale].browseByPipelineTitle });
    const cards = section.getByRole("list").first().locator(":scope > li");
    await expect(cards).toHaveCount(index.pipeline_stages.length);
    for (const [i, stage] of index.pipeline_stages.entries()) {
      const products = index.categories.filter((c) => c.pipeline.includes(stage.id))
        .reduce((n, c) => n + c.products, 0);
      const card = cards.nth(i).getByRole("link");
      await expect(card).toHaveAttribute("href", `/browse?stage=${stage.id}`);
      await expect(card).toHaveText(new RegExp(`^${String(i + 1).padStart(2, "0")}\\s*${escape(label(stage.label,
        locale))}\\s*${escape(label(stage.description, locale))}\\s*${products}\\s`));
    }
    const heights = await cards.getByRole("link").evaluateAll((links) =>
      [...new Set(links.map((a) => Math.round(a.getBoundingClientRect().height)))]);
    expect(heights).toHaveLength(1);
    const domains = page.getByRole("navigation", { name: MESSAGES[locale].browseByDomainTitle }).getByRole("link");
    const counted = index.domains.map((d) => ({ d, n: index.categories.filter((c) => c.domain === d.id)
      .reduce((n, c) => n + c.products, 0) })).filter(({ n }) => n > 0);
    expect(await domains.evaluateAll((links) => links.map((a) => a.getAttribute("href"))))
      .toEqual(counted.map(({ d }) => `/browse?domain=${d.id}`));
    await expect(domains)
      .toHaveText(counted.map(({ d, n }) => new RegExp(`^${escape(label(d.label, locale))}\\s*${n}\\s`)));
  });
});

