import { randomUUID } from "node:crypto";
import { expect } from "@playwright/test";
import { radar, rows } from "../../fixture.ts";
import { inEachLocale, MESSAGES } from "../../messages.ts";
import { decide, founderTest as test, noAxeViolations } from "./admin.ts";

const maker = rows<{ slug: string; website?: string }>("organizations.jsonl")
  .find((o) => o.website === "https://example.com");
const WIDGET = rows<{ subject: string; value: string }>("names.jsonl")
  .find((n) => n.subject === "prd_0000000002")?.value ?? "";
const UNREAD = "prd_0000000005";
const CHECKED = {
  en: { intl: "en-GB", filed: 0, reason: "The maker's page gives Widget Two's mass as 93 g", shown: /\(g\)\s*93/,
    file: 2, href: "https://example.com/media/widget-two.png",
        review: "leave out" },
  fr: { intl: "fr-FR", filed: 0, reason: "The maker's page gives Widget Two's reach as 125 mm", shown: /\(mm\)\s*125/,
    file: 2, href: "https://example.com/media/widget-two.pdf",
        review: "one by one" },
} as const;
const ZONE = "Asia/Kolkata";
const counted = (message: string): RegExp =>
  new RegExp(message.replace(/[.*+?^$()|[\]\\]/g, "\\$&").replace(/\{\w+\}/g, "\\d+"));

inEachLocale("agents", (locale) => {
  const T = MESSAGES[locale];
  const { intl, filed: nth, reason, shown, file, href, review } = CHECKED[locale];
  test.use({ timezoneId: ZONE });

  test("the founder issues a token, sees it once, and revokes it", async ({ page }) => {
    test.setTimeout(120_000);
    const run = `${locale}-${randomUUID().slice(0, 8)}`;
    const agent = `Scout ${run}`;
    await page.goto("/admin/agents");
    await expect(page.getByRole("heading", { level: 1, name: T.adminAgentsTitle })).toBeVisible();

    await page.getByLabel(T.adminAgentsName).fill(agent);
    await page.getByLabel(T.adminAgentsScope).selectOption("propose");
    await page.getByLabel(T.adminAgentsExpires).fill("2099-01-01");
    await page.getByLabel(T.adminAgentsProposals).fill("7");
    await page.getByRole("button", { name: T.adminAgentsIssue, exact: true }).click();
    const issued = page.getByRole("region", { name: T.adminAgentsIssued.replace("{name}", agent) });
    await expect(issued).toContainText(T.adminAgentsShownOnce);
    const token = (await issued.locator("code").innerText()).trim();
    expect(token).toMatch(/^mvr_[0-9a-f]{32}$/);
    await issued.getByRole("button", { name: T.adminAgentsCopy }).click();
    await expect(issued.getByRole("status")).toHaveText(T.adminAgentsCopied);
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(token);

    const row = page.getByRole("row").filter({ hasText: agent });
    await expect(row).toContainText(T.adminAgentsScopePropose);
    await expect(row).toContainText(T.adminAgentsActive);
    await expect(row).toContainText(T.adminAgentsLimitsOf.replace("{requests}", "60").replace("{proposals}", "7"));
    await page.reload();
    await expect(row).toContainText(T.adminAgentsActive);
    await expect(page.getByText(token)).toHaveCount(0);

    await row.getByRole("button", { name: T.adminAgentsRevokeName.replace("{name}", agent) }).click();
    await expect(row).toContainText(T.adminAgentsRevokeConfirm.replace("{name}", agent));
    await row.getByRole("button", { name: T.adminAgentsKeep }).click();
    await expect(row).toContainText(T.adminAgentsActive);
    await row.getByRole("button", { name: T.adminAgentsRevokeName.replace("{name}", agent) }).click();
    await row.getByRole("button", { name: T.adminAgentsRevokeYes }).click();
    await expect(row).toContainText(T.adminAgentsRevoked);
    await expect(row.getByRole("button")).toHaveCount(0);

    await noAxeViolations(page, ["/admin/agents"]);
  });

  test("the tokens list pages at 20 rows, and reads each page alone", async ({ page }) => {
    test.setTimeout(120_000);
    const total = (): number => JSON.parse(radar("--json", "agent-token", "list")).total;
    const created: string[] = [];
    for (let n = total(); n <= 20; n += 1) {
      const res = JSON.parse(radar("--json", "agent-token", "create", `Pager ${locale} ${n}`, "--scope", "read",
        "--expires", "2099-01-01"));
      created.push(res.agent.id);
    }
    const all = total();
    const read: string[] = [];
    page.on("request", (r) => {
      const url = new URL(r.url());
      if (r.method() === "GET" && url.pathname === "/api/admin/agents") read.push(url.search);
    });
    try {
      await page.goto("/admin/agents");
      const listed = page.locator("tbody tr");
      await expect(listed).toHaveCount(20);
      const pager = page.getByRole("navigation", { name: T.paginationLabel });
      await expect(pager).toContainText(T.paginationRows.replace("{start}", "1").replace("{end}", "20")
        .replace("{total}", String(all)));
      await pager.getByRole("button", { name: T.paginationNext }).click();
      await expect(page).toHaveURL(/\/admin\/agents\?page=2$/);
      await expect(listed).toHaveCount(Math.min(20, all - 20));
      expect(read).toEqual(["", "?cursor=20"]);
    } finally {
      const base = process.env.MVR_FIRESTORE_DOCS;
      if (base) {
        await Promise.all(created.map((id) =>
          page.request.delete(`${base}/agent_tokens/${id}`, { headers: { Authorization: "Bearer owner" } })));
      }
    }
  });

  test("the founder runs research, reads its log, reviews its bundle and sees what was approved on the product "
    + "page", async ({ page }) => {
    test.setTimeout(200_000);
    await page.goto("/admin/research");
    await expect(page.getByRole("heading", { level: 1, name: T.adminResearchTitle })).toBeVisible();
    await page.getByLabel(T.adminResearchScope).selectOption("maker");
    await page.getByLabel(T.adminResearchKey).fill(maker?.slug ?? "");
    await page.getByRole("button", { name: T.adminResearchRunNow }).click();

    await expect(page).toHaveURL(/\/admin\/research\/runs\/research-[0-9a-f]{16}$/, { timeout: 60_000 });
    await expect(page.getByRole("heading",
      { level: 1, name: T.adminResearchRunTitle.replace("{scope}", maker?.slug ?? "") })).toBeVisible();
    await expect(page.locator("article header")).toContainText(T.adminResearchDone);
    const started = page.locator("article header time").first();
    const at = (await started.getAttribute("datetime")) ?? "";
    const clock = new Intl.DateTimeFormat(intl, { dateStyle: "medium", timeStyle: "medium", timeZone: ZONE });
    await expect(started).toHaveText(clock.format(new Date(at)));
    const { ended_at: ended, filed: ids }: { ended_at: string; filed: string[] } =
      JSON.parse(radar("--json", "research", "log", page.url().split("/").at(-1) ?? ""));
    await expect(page.locator("article header"))
      .toContainText(T.adminEnded.replace("{at}", clock.format(new Date(ended))));
    const log = page.getByRole("region", { name: T.adminResearchLog });
    await expect(log.getByRole("listitem").filter({ hasText: "https://example.com/products/widget-two" }).first())
      .toContainText(T.adminResearchStepRead);
    await expect(log.getByRole("listitem").filter({ hasText: "robots.txt disallows it" }))
      .toContainText(T.adminResearchStepSkipped);
    const filed = page.getByRole("region", { name: counted(T.adminResearchFiled) });
    await expect(filed).toContainText(counted(T.adminResearchFiles));
    await expect(log.getByRole("listitem").filter({ hasText: T.adminResearchStepDatasheet }).first()).toBeVisible();
    const runPath = new URL(page.url()).pathname;
    const runId = runPath.split("/").at(-1) ?? "";

    await filed.getByRole("link", { name: T.adminResearchBundle }).click();
    await expect(page).toHaveURL(new RegExp(`/admin/queue/bundles/${runId}$`));
    const bundlePath = new URL(page.url()).pathname;
    await expect(page.getByRole("heading",
      { level: 1, name: T.adminBundleTitle.replace("{count}", String(ids.length)) })).toBeVisible();
    await page.locator(`a[href="/admin/queue/${ids[nth]}"]`).click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText(reason);
    await expect(page.locator("article header p").first()).toContainText(`research (${T.adminActorAgent})`);
    await page.getByRole("link", { name: runId, exact: true }).click();
    const kept = [ids[nth], ids[file]];
    const left = ids.filter((id) => !kept.includes(id));
    const note = `Not now, checked on the maker's page (${locale})`;
    if (review === "leave out") {
      for (const id of left) await page.getByLabel(T.adminLeaveOut.replace("{id}", id)).check();
      await page.getByLabel(T.adminNote).fill(note);
      await page.getByRole("button", { name: (left.length === 1 ? T.adminApproveRestOne : T.adminApproveRestOther)
        .replace("{count}", String(left.length)) }).click();
    } else {
      for (const id of kept) {
        await page.locator(`a[href="/admin/queue/${id}"]`).click();
        await decide(page, T, `Checked on the maker's page (${locale})`);
        await page.getByRole("link", { name: runId, exact: true }).click();
      }
      await page.getByLabel(T.adminNote).fill(note);
      await page.getByRole("button", { name: T.adminRejectBundle }).click();
    }
    for (const id of ids) {
      const member = page.getByRole("listitem").filter({ has: page.locator(`a[href="/admin/queue/${id}"]`) });
      await expect(member)
        .toContainText(kept.includes(id) ? T.adminStatusApproved : T.adminStatusRejected, { timeout: 60_000 });
    }
    await expect(page.getByRole("alert")).toHaveCount(0);
    await page.locator(`a[href="/admin/queue/${left[0]}"]`).click();
    await expect(page.locator("article header")).toContainText(note);

    await page.goto(`/browse?q=${encodeURIComponent(WIDGET)}`);
    await page.getByRole("main").getByRole("link", { name: WIDGET, exact: true }).first().click();
    await expect(page.getByRole("main")).toContainText(shown);
    await page.getByRole("link", { name: T.historyLink }).click();
    await expect(page.locator("ol.history > li").first()).toContainText(reason);
    await page.goBack();
    await expect(page.locator(`section.media a[href="${href}"]`)).toBeVisible();

    await page.goto("/admin/research");
    await page.getByLabel(T.adminResearchScope).selectOption("product");
    await page.getByLabel(T.adminResearchKey).fill(UNREAD);
    await page.getByRole("button", { name: T.adminResearchRunNow }).click();
    await expect(page.getByRole("heading", { level: 1, name: T.adminResearchRunTitle.replace("{scope}", UNREAD) }))
      .toBeVisible({ timeout: 60_000 });
    await expect(page.locator("article header")).toContainText(T.adminResearchBlocked);

    await noAxeViolations(page, ["/admin/research", runPath, bundlePath]);
  });
});
