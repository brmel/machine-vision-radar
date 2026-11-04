import { randomInt, randomUUID } from "node:crypto";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { expect } from "@playwright/test";
import { radar, rows } from "../../fixture.ts";
import { inEachLocale, MESSAGES } from "../../messages.ts";
import { decide, founderTest as test, noAxeViolations } from "./admin.ts";

interface Row { id: string; slug: string; subject: string; url: string; is_primary?: boolean;
  value: { quantity?: { value?: number } } & string;
  source_refs: string[] }
const names = new Map(rows<Row>("names.jsonl").filter((n) => n.is_primary).map((n) => [n.subject, n.value]));
const product = [...rows<Row>("products.jsonl")].sort((a, b) => (names.get(a.id) ?? "").toLowerCase()
  .localeCompare((names.get(b.id) ?? "").toLowerCase()))[0];
const claim = rows<Row>("claims.jsonl").find((c) => c.subject === product?.id && c.value.quantity?.value !== undefined);
const source = rows<Row>("sources.jsonl").find((s) => s.id === claim?.source_refs[0]);

async function connected(base: string, token: string): Promise<Client> {
  const client = new Client({ name: "mvradar-e2e", version: "1.0.0" });
  await client.connect(new StreamableHTTPClientTransport(new URL("/api/mcp", base),
    { requestInit: { headers: { Authorization: `Bearer ${token}` } } }));
  return client;
}

async function answer<T>(client: Client, name: string, args: Record<string, unknown>): Promise<T> {
  const result = await client.callTool({ name, arguments: args });
  expect(result.isError, JSON.stringify(result.content)).toBeFalsy();
  // Justification (typed boundary): the client validated structuredContent against the tool's generated output schema.
  return result.structuredContent as T;
}

inEachLocale("an outside agent over MCP", (locale) => {
  const T = MESSAGES[locale];

  test("an agent searches, finds a source and proposes; the founder approves; the page shows it; a revoked token is "
    + "refused", async ({ page, baseURL }) => {
    test.setTimeout(120_000);
    const run = `${locale}-${randomUUID().slice(0, 8)}`;
    const agent = `Grok Bot ${run}`;
    const issued: { agent: { id: string }; token: string } =
      JSON.parse(radar("--json", "agent-token", "create", agent, "--scope", "propose", "--expires", "2099-01-01"));
    const client = await connected(baseURL ?? "", issued.token);

    const tools = (await client.listTools()).tools;
    expect(tools.map((t) => [t.name, t.annotations?.readOnlyHint, Boolean(t.title)])).toEqual(
      ["search_products", "get_product", "search_sources", "submit_proposal", "list_my_proposals",
        "get_proposal_status"].map((n) => [n, n !== "submit_proposal", true]),
    );

    await page.goto("/agents");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(T.agentsTitle);
    await expect(page.getByText(/^https?:\/\/.+\/api\/mcp$/)).toBeVisible();
    await noAxeViolations(page, ["/agents"]);
    const found = await answer<{ hits: { id: string }[] }>(client, "search_products",
      { query: names.get(product?.id ?? "") ?? "" });
    expect(found.hits.map((h) => h.id)).toContain(product?.id);
    const cited = await answer<{ sources: { id: string }[] }>(client, "search_sources", { url: source?.url ?? "" });
    expect(cited.sources.map((s) => s.id)).toContain(source?.id);

    const value = 611 + randomInt(80);
    const record = { ...Object.fromEntries(Object.entries(claim ?? {}).filter(([k]) => k !== "version")),
      value: { quantity: { ...claim?.value.quantity, value } } };
    const reason = `The maker's datasheet, revision ${run}`;
    const filed = await answer<{ id: string; status: string; author: string }>(client, "submit_proposal", {
      files_on: "update", reason, subject: product?.id,
      changeset: JSON.stringify({ changes: [{ op: "put", entity: record, reason: "Datasheet revision",
        source_refs: [cited.sources[0].id] }] }),
    });
    expect([filed.status, filed.author]).toEqual(["suggested", agent]);
    expect((await answer<{ proposals: { id: string }[] }>(client, "list_my_proposals", {})).proposals.map((p) => p.id))
      .toEqual([filed.id]);

    await page.goto("/admin/queue");
    await page.getByRole("link", { name: new RegExp(reason) }).click();
    await expect(page.locator("article header p").first()).toContainText(`${agent} (${T.adminActorAgent})`);
    await expect(page.getByText(`${T.adminSources}: ${source?.id}`)).toBeVisible();
    await expect(page.getByRole("cell", { name: String(value) })).toBeVisible();
    await decide(page, T, `Checked against the datasheet (${locale})`);
    await noAxeViolations(page, [`/admin/queue/${filed.id}`]);

    expect((await answer<{ status: string }>(client, "get_proposal_status", { id: filed.id })).status).toBe("approved");
    await page.goto(`/product/${product?.slug}`);
    await expect(page.getByRole("main")).toContainText(String(value));

    radar("agent-token", "revoke", issued.agent.id);
    await expect(client.listTools()).rejects.toThrow(/the agent token is refused: revoked on/);
    await expect(connected(baseURL ?? "", issued.token)).rejects.toThrow(/revoked on/);
    await client.close();
    radar("proposal", "retract", filed.id, "--note", "End-to-end check done");
  });
});
