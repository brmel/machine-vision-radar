import { randomInt, randomUUID } from "node:crypto";
import { expect, type Page } from "@playwright/test";
import { LANGUAGES } from "../../../src/domain/languages.ts";
import { registryFile, rows } from "../../fixture.ts";
import { inEachLocale, MESSAGES } from "../../messages.ts";
import { addLabel, asFounder, citeNewSource, decide, fieldLabel, fileApproved, founderTest, kindLabel, modelKeysShown,
  noAxeViolations, test } from "./admin.ts";

interface Row { id: string; slug: string; category: string; subject: string; spec_key: string; product: string;
  org: string; role: string; is_primary?: boolean; scheme: string;
  value: { quantity?: { value?: number; max?: number } }; source_refs: string[]; website?: string }
const vocabulary = (name: string) =>
  registryFile<{ id: string; mime_types?: string[]; owns?: boolean }[]>(`vocabularies/${name}.json`);
const DOCUMENT_KINDS = vocabulary("document_kinds");
const PDF_KIND = DOCUMENT_KINDS.find((k) => k.mime_types?.includes("application/pdf"))?.id ?? "";
const IMAGE_KIND = DOCUMENT_KINDS.find((k) => k.mime_types?.some((m) => m.startsWith("image/")))?.id ?? "";
const OWNED_BY = vocabulary("org_relation_types").find((t) => t.owns)?.id ?? "";

const claim = rows<Row>("claims.jsonl").find((c) => c.value.quantity?.value !== undefined);
const product = rows<Row>("products.jsonl").find((p) => p.id === claim?.subject);
const role = rows<Row>("product_org_roles.jsonl").find((r) => r.product === product?.id);
const siteless = rows<Row>("organizations.jsonl").find((o) => !o.website);
const maker = rows<Row>("organizations.jsonl").find((o) => o.id === role?.org);
const versioned = rows<Row>("product_versions.jsonl")[0];

async function shown(page: Page): Promise<string> {
  const doc = await (await page.request.get(`${process.env.MVR_FIRESTORE_DOCS}/public_products/${product?.id}`)).json();
  return String(doc.fields.json.stringValue);
}

inEachLocale("the review queue", (locale) => {
  const T = MESSAGES[locale];

  test("a report becomes an approved change, retracted and undone; "
    + "a product is added with its media file and rolled back", async ({ page }) => {
    test.setTimeout(120_000);
    await page.addInitScript(() => {
      window.addEventListener("securitypolicyviolation", (e) => {
        const seen: string[] = JSON.parse(localStorage.getItem("cspViolations") ?? "[]");
        localStorage.setItem("cspViolations",
          JSON.stringify([...seen, `${e.effectiveDirective} blocked ${e.blockedURI}`]));
      });
    });
    const run = `${locale}-${randomUUID().slice(0, 8)}`;

    await page.goto(`/product/${product?.slug}`);
    const message = `The value is wrong on the datasheet (${run}).`;
    const unfounded = `The colour is wrong (${run}).`;
    for (const [said, words] of [[T.reportFiled, message], [T.reportCounted, message], [T.reportFiled, unfounded]]) {
      await page.getByRole("button", { name: T.reportErrorAction }).click();
      await page.getByLabel(T.reportMessage).fill(words);
      await page.getByRole("button", { name: T.reportSend }).click();
      await expect(page.getByRole("status").filter({ hasText: said })).toBeVisible();
      await page.getByRole("button", { name: T.reportErrorAction }).click();
    }

    await asFounder(page, T, `founder-${run}@example.com`);
    await expect(page.getByRole("heading", { level: 1, name: T.adminQueueTitle })).toBeVisible();

    const chooseAll = page.getByLabel(T.adminChooseAll, { exact: true });
    await chooseAll.check();
    const chosen = await page.getByRole("checkbox", { name: T.adminChoose.replace("{id}", "prp_") }).count();
    const approveChosen = page.getByRole("button", { name: (chosen === 1 ? T.adminApproveChosenOne
      : T.adminApproveChosenOther).replace("{count}", String(chosen)) });
    await expect(approveChosen).toBeVisible();
    await chooseAll.uncheck();
    await expect(approveChosen).toHaveCount(0);

    await page.getByRole("link", { name: new RegExp(unfounded.replace(/[().]/g, "\\$&")) }).click();
    await decide(page, T, `No source says so (${locale})`, T.adminReject, T.adminStatusRejected);
    await page.goto("/admin/queue");
    await page.getByRole("link", { name: new RegExp(message.replace(/[().]/g, "\\$&")) }).click();
    await expect(page.getByText(T.adminNoChange)).toBeVisible();
    const quantity = claim?.value.quantity ?? {};
    const value = 4000.5 + randomInt(999);
    const changed = { ...Object.fromEntries(Object.entries(claim ?? {}).filter(([k]) => k !== "version")),
      value: { quantity: { ...quantity, value } } };
    await page.getByLabel(T.adminChangeset).fill(JSON.stringify({ changes: [{ op: "put", entity: changed,
      reason: "Datasheet", actor_kind: "human", actor: "x", source_refs: claim?.source_refs }] }));
    await decide(page, T, `Checked against the datasheet (${locale})`, T.adminSaveEdit, T.adminStatusSuggested);
    await expect(page.getByRole("cell", { name: String(value) })).toBeVisible();
    const before = await shown(page);
    await decide(page, T, `Approved (${locale})`);
    expect(await shown(page)).toContain(`"value":${value}`);
    await decide(page, T, `Withdrawn by the vendor (${locale})`, T.adminRetract, T.adminStatusRetracted);
    expect(await shown(page)).toBe(before);

    const website = `https://example.com/${run}`;
    await page.goto(`/admin/records/${siteless?.id}`);
    await page.getByLabel(fieldLabel("Organization", "website", locale), { exact: true }).fill(website);
    await citeNewSource(page, T, website);
    await fileApproved(page, T, "Its own site");
    await page.goto(`/vendor/${siteless?.slug}`);
    await expect(page.getByRole("link", { name: T.officialWebsite })).toHaveAttribute("href", website);

    await page.goto("/admin/records/new/Product");
    await page.getByLabel(`${T.adminName} *`).fill(`Halden Widget ${run}`);
    await page.getByLabel(fieldLabel("Product", "kind", locale)).selectOption({ index: 1 });
    await page.getByLabel(fieldLabel("Product", "category", locale)).selectOption(product?.category ?? "");
    await page.getByLabel(fieldLabel("Product", "slug", locale)).fill(`${maker?.slug}__halden-widget-${run}`);
    expect(await modelKeysShown(page)).toEqual([]);
    await page.getByLabel(`${T.adminMakerOrg} *`).fill(role?.org ?? "");
    await page.getByLabel(`${T.adminMakerRole} *`).selectOption(role?.role ?? "");
    await citeNewSource(page, T, `https://example.com/${run}/widget.pdf`);
    const made = await fileApproved(page, T, "A new product");
    const attach = async (name: string, mimeType: string, body: string, kind: string) => {
      await page.goto(`/admin/records/${made}`);
      await page.getByRole("link", { name: addLabel(T, "Document", "subjects", locale) }).click();
      await page.getByLabel(`${T.adminMediaFile} *`).setInputFiles({ name, mimeType, buffer: Buffer.from(body) });
      await expect(page.getByText(/^sha256 [0-9a-f]{64}/)).toBeVisible();
      await expect(page.getByLabel(fieldLabel("Document", "subjects", locale))).toHaveValue(JSON.stringify([made]));
      await page.getByLabel(fieldLabel("Document", "kind", locale)).selectOption(kind);
      await page.getByLabel(fieldLabel("Document", "rights", locale)).selectOption({ index: 1 });
      expect(await modelKeysShown(page)).toEqual([]);
    };
    await attach("manual.pdf", "application/pdf", `%PDF-1.4\n% a fictional manual ${locale}\n`, PDF_KIND);
    await fileApproved(page, T, "The maker's manual");

    await page.goto(`/admin/records/${made}`);
    await expect(page.getByRole("heading", { level: 3, name: kindLabel("Document", locale) })).toBeVisible();
    await page.getByLabel(fieldLabel("Product", "website_url", locale), { exact: true })
      .fill(`https://example.com/${run}/halden-widget`);
    await citeNewSource(page, T, `https://example.com/${run}/halden-widget`);
    await fileApproved(page, T, "Its page");
    await page.goto(`/admin/records/${made}/history`);
    await page.getByRole("combobox", { name: T.adminDiffFrom, exact: true }).selectOption("1");
    await page.getByRole("combobox", { name: T.adminDiffTo, exact: true }).selectOption("2");
    await page.getByRole("button", { name: T.adminCompare }).click();
    await expect(page.getByRole("rowheader", { name: "website_url" })).toBeVisible();
    await page.getByRole("button", { name: T.adminRollbackTo.replace("{version}", "1") }).click();
    await page.getByLabel(T.adminReason).fill("The page moved");
    await page.getByRole("button", { name: T.adminRollbackTo.replace("{version}", "1") }).last().click();
    await decide(page, T, `Back to v1 (${locale})`);
    await page.goto(`/admin/records/${made}/history`);
    await expect(page.getByRole("listitem").first()).toContainText("v3");

    await attach("widget.png", "image/png", `\x89PNG\r\n\x1a\n fictional image ${locale}\n`, IMAGE_KIND);
    await fileApproved(page, T, "Product photo");

    await page.goto(`/admin/records/${made}`);
    await page.getByRole("button", { name: T.adminUseAsThumbnail }).first().click();
    await page.getByLabel(`${T.adminSourceCited} *`).selectOption({ index: 0 });
    await fileApproved(page, T, "Use as thumbnail");

    for (const next of ["dark", "light"]) {
      await page.goto(`/product/${maker?.slug}__halden-widget-${run}`);
      await expect(page.locator(".rounded-control img")).toBeVisible();
      await page.evaluate((t) => localStorage.setItem("machineVisionRadar.themePreference", t), next);
    }

    await page.goto(`/category/${product?.category}`);
    await expect(page.locator("article").filter({ hasText: `Halden Widget ${run}` }).locator("img")).toBeVisible();

    await page.goto("/admin/queue");
    await page.getByRole("link", { name: T.adminLogTitle }).click();
    await expect(page).toHaveURL(/\/admin\/queue\/log$/);
    await page.reload();
    for (const action of [T.adminActionSubmit, T.adminActionEdit, T.adminStatusApproved, T.adminStatusRejected,
      T.adminStatusRetracted]) await expect(page.getByText(action, { exact: true }).first()).toBeVisible();
    expect(await page.getByText(T.adminStatusApproved, { exact: true }).count()).toBeGreaterThanOrEqual(6);
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("cspViolations") ?? "[]"))).toEqual([]);
    await page.goto(`/admin/queue/log?actor=${encodeURIComponent(`nobody ${run}`)}`);
    await expect(page.getByText(T.adminLogEmpty, { exact: true })).toBeVisible();

    await noAxeViolations(page, ["/admin/queue", "/admin/queue/log", `/admin/records/${made}`,
      `/admin/records/${made}/history`, "/admin/products", "/admin/organizations", "/admin/media",
      "/admin/records/new/Organization", "/admin/records/new/Document"]);
  });

  founderTest("the grid sets one spec across a category's products as one proposal, "
    + "a value or none with its reason, which approved changes the records", async ({ page }) => {
    const run = `${locale}-${randomUUID().slice(0, 8)}`;
    const value = String(randomInt(1000, 9000));
    const grid = `/admin/grid?category=${product?.category}&spec=${claim?.spec_key}`;
    const first = () => page.getByRole("main").getByRole("listitem").first().getByRole("spinbutton").first();
    const none = () => page.getByRole("main").getByRole("listitem").nth(1)
      .getByRole("combobox", { name: new RegExp(`${T.adminNoneBecause}$`) });
    await page.goto(grid);
    await expect(page.getByRole("heading", { level: 1, name: T.adminGridTitle })).toBeVisible();
    const row = page.getByRole("main").getByRole("listitem").first();
    const unit = await row.getByRole("combobox", { name: new RegExp(T.adminUnit) }).boundingBox();
    expect((await first().boundingBox())?.width).toBeGreaterThan(unit?.width ?? Infinity);
    await first().fill(value);
    await none().selectOption({ index: 1 });
    const reason = await none().inputValue();
    await citeNewSource(page, T, `https://example.com/${run}/grid`);
    await page.getByLabel(`${T.adminReason} *`).fill(`The grid's ${run}`);
    await page.getByRole("button", { name: T.adminFile }).click();
    await decide(page, T, `Checked: the grid's ${run}`);
    await page.goto(grid);
    await expect(first()).toHaveValue(value);
    await expect(none()).toHaveValue(reason);
    const held = new Set(rows<Row>("products.jsonl").map((p) => p.category));
    const empty = registryFile<{ id: string }[]>("categories.json").find((c) => !held.has(c.id));
    await page.goto(`/admin/grid?category=${empty?.id}&spec=${claim?.spec_key}`);
    await expect(page.getByText(T.adminNoRecords)).toBeVisible();
    await expect(page.getByRole("button", { name: T.adminFile })).toHaveCount(0);
  });

  founderTest("an organization and each record about it are added, edited and deleted, its history kept; "
    + "so is a product version", async ({ page }) => {
    test.setTimeout(240_000);
    const run = `${locale}-${randomUUID().slice(0, 8)}`;
    const label = (entity: string, field: string) => page.getByLabel(fieldLabel(entity, field, locale));
    const add = (entity: string, field: string) =>
      page.getByRole("link", { name: addLabel(T, entity, field, locale) }).click();
    const remove = async (path: string, reason: string) => {
      await page.goto(path);
      await page.getByLabel(T.adminReason, { exact: true }).fill(reason);
      await page.getByRole("button", { name: T.adminDelete }).click();
      await decide(page, T, `Checked: ${reason}`);
    };

    await page.goto("/admin/records/new/Organization");
    await label("Organization", "kind").selectOption({ index: 1 });
    await label("Organization", "name").fill(`Halden Optics ${run}`);
    await label("Organization", "slug").fill(`halden-optics-${run}`);
    await citeNewSource(page, T, `https://example.com/${run}/about`);
    const org = await fileApproved(page, T, "A new maker");

    await page.goto(`/admin/records/${org}`);
    await label("Organization", "kind").selectOption({ index: 2 });
    await label("Organization", "name").fill(`Halden Imaging ${run}`);
    await expect(label("Organization", "slug")).toBeDisabled();
    const summary = page.getByRole("group", { name: fieldLabel("Organization", "summary", locale) });
    for (const language of LANGUAGES) await summary.getByLabel(language.name)
      .fill(`Lenses (${language.code}, ${run}).`);
    await page.getByLabel(fieldLabel("Organization", "website", locale), { exact: true })
      .fill(`https://example.com/${run}`);
    await label("Organization", "country").fill("DE");
    await label("Organization", "founded").fill("1998");
    await citeNewSource(page, T, `https://example.com/${run}/history`);
    await fileApproved(page, T, "Its own words");

    const item = 1_000_000 + randomInt(999_999);
    for (const [entity, value, corrected, scheme] of [["Name", `Halden ${run}`, `Halden ${run} (2)`, ""],
      ["AltName", `HO ${run}`, `HO ${run} (2)`, ""], ["Identifier", `Q${item}`, `Q${item + 1}`, "wikidata"]] as const) {
      await page.goto(`/admin/records/${org}`);
      await add(entity, "subject");
      if (scheme) await label(entity, "scheme").selectOption(scheme);
      await label(entity, "value").fill(value);
      await citeNewSource(page, T, `https://example.com/${run}/${entity}`);
      const made = await fileApproved(page, T, `Its ${entity}`);
      await page.goto(`/admin/records/${made}`);
      await label(entity, "value").fill(corrected);
      await citeNewSource(page, T, `https://example.com/${run}/${entity}/2`);
      await fileApproved(page, T, `Its ${entity}, corrected`);
    }

    await page.goto(`/admin/records/${org}`);
    await add("OrgRelation", "from_org");
    await label("OrgRelation", "type").selectOption(OWNED_BY);
    await label("OrgRelation", "to_org").fill(role?.org ?? "");
    await citeNewSource(page, T, `https://example.com/${run}/acquired`);
    const owned = await fileApproved(page, T, "Acquired");
    await page.goto(`/admin/records/${owned}`);
    await label("OrgRelation", "valid_from").fill("2024");
    await fileApproved(page, T, "Acquired in 2024");

    await page.goto(`/admin/records/${org}`);
    for (const entity of ["Name", "AltName", "Identifier", "OrgRelation"])
      await expect(page.getByRole("heading", { level: 3, name: kindLabel(entity, locale), exact: true })).toBeVisible();
    await remove(`/admin/records/${org}`, "Not a maker after all");
    await page.goto(`/admin/records/${org}/history`);
    await expect(page.getByRole("listitem").first()).toContainText("Not a maker after all");
    await expect(page.getByRole("listitem")).toHaveCount(3);

    await page.goto(`/admin/records/${versioned?.product}`);
    await add("ProductVersion", "product");
    await label("ProductVersion", "kind").selectOption({ index: 1 });
    await label("ProductVersion", "label").fill(`9.${randomInt(999)}.0`);
    await label("ProductVersion", "scheme").selectOption(versioned?.scheme ?? "");
    await citeNewSource(page, T, `https://example.com/${run}/release`);
    const version = await fileApproved(page, T, "Released");
    await page.goto(`/admin/records/${version}`);
    await label("ProductVersion", "released").fill("2026-05");
    await fileApproved(page, T, "Its release date");
    await remove(`/admin/records/${version}`, "Never shipped");
    await page.goto(`/admin/records/${version}/history`);
    await expect(page.getByRole("listitem").first()).toContainText("Never shipped");
  });
});
