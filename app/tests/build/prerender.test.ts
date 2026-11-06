import { execFileSync } from "node:child_process";
import { cpSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { availableParallelism, tmpdir } from "node:os";
import { join, relative } from "node:path";
import { DEV, resolveFirestoreDocs } from "../../scripts/head.ts";
import { describe, expect, it, vi } from "vitest";
import { rows } from "../fixture.ts";
import { DEFAULT_MESSAGES } from "../../src/shell/i18n/messages.ts";

const APP = join(import.meta.dirname, "..", "..");
const ORIGIN = "https://example.com";
const TEMPLATE = '<!doctype html><html><head><title>t</title></head><body><div id="root"></div></body></html>';
const FIRESTORE = process.env.FIRESTORE_EMULATOR_HOST;
const MEDIA = { MVR_MEDIA_BASE: "http://127.0.0.1:9195", MVR_STORAGE_BUCKET: "demo-mvradar.appspot.com" };

function prerender(env: Record<string, string>, heapMiB?: number): { out: string; rss: number; requests: string[] } {
  const out = mkdtempSync(join(tmpdir(), "mvr-prerender-"));
  writeFileSync(join(out, "index.html"), TEMPLATE);
  mkdirSync(join(out, "read-model"));
  writeFileSync(join(out, "read-model", "index.json"), "{}");
  const probe = join(out, "..", `${relative(tmpdir(), out)}-rss.mjs`);
  writeFileSync(`${probe}.log`, "");
  writeFileSync(probe, `import fs from "node:fs"; import { isMainThread } from "node:worker_threads";
const real = globalThis.fetch;
globalThis.fetch = (url, init) => {
  const sent = \`\${init?.method ?? "GET"} \${decodeURIComponent(String(url))}\\n\`;
  fs.appendFileSync(${JSON.stringify(`${probe}.log`)}, sent);
  return real(url, init);
};
if (isMainThread) process.on("exit", () =>
  fs.writeFileSync(${JSON.stringify(`${probe}.txt`)}, String(process.resourceUsage().maxRSS * 1024)));`);
  execFileSync("node", ["--experimental-strip-types", `--import=${probe}`,
    ...(heapMiB ? [`--max-old-space-size=${heapMiB}`] : []), "scripts/prerender/main.ts"], {
    cwd: APP, stdio: "pipe", env: { ...process.env, MVR_SITE_URL: ORIGIN, MVR_PRERENDER_OUT: out, ...env },
  });
  return { out, rss: Number(readFileSync(`${probe}.txt`, "utf-8")),
    requests: readFileSync(`${probe}.log`, "utf-8").split("\n").filter(Boolean) };
}

function fixture(extra = 16): string {
  const printed = execFileSync("python3",
    ["-m", "radar.tests.fixtures.fixture_category", mkdtempSync(join(tmpdir(), "mvr-fixture-")), String(extra)],
    { cwd: DEV, encoding: "utf8", env: { ...process.env, ...MEDIA } });
  return join(printed.trim().split("\n").slice(-1)[0], "..");
}

const text = (html: string): string => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
const locs = (xml: string): string[] => [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
const urls = (out: string): Map<string, string | undefined> => new Map(
  locs(readFileSync(join(out, "sitemap.xml"), "utf-8"))
    .flatMap((f) => [...readFileSync(join(out, new URL(f).pathname), "utf-8").matchAll(
    /<loc>([^<]+)<\/loc>\n(?:\s*<lastmod>([^<]+)<\/lastmod>)?/g)].map((m) => [m[1], m[2]] as const)));

interface Row { id: string; slug: string; version: number; subject?: string; entity?: string; actor_kind?: string;
  recorded_at?: string; retrieved_at?: string }

describe("prerender", () => {
  it("writes every fixture product and a sitemap of its indexable ones whose lastmod follows the Change events", () => {
    const dir = fixture();
    const { out } = prerender({ MVR_READ_MODEL_DIR: join(dir, "dist", "public") });
    const sitemap = urls(out);
    const products = rows<Row>("products.jsonl", dir);
    const viewOf = (id: string) =>
      JSON.parse(readFileSync(join(dir, "dist", "public", "products", `${id}.json`), "utf-8"));
    for (const p of products) {
      expect(readFileSync(join(out, "product", `${p.slug}.html`), "utf-8")).toContain('id="mvr-product"');
      expect(sitemap.has(`${ORIGIN}/product/${p.slug}`), p.slug).toBe(viewOf(p.id).indexable);
    }
    const family = products.find((p) => viewOf(p.id).models.length > 1)!;
    const compared = readFileSync(join(out, "compare", `${family.slug}.html`), "utf-8");
    expect(compared).toContain(`<link rel="canonical" href="${ORIGIN}/compare/${family.slug}"`);
    expect(compared.match(/<th\b/g)?.length).toBeGreaterThan(viewOf(family.id).models.length);
    expect(sitemap.has(`${ORIGIN}/compare/${family.slug}`)).toBe(viewOf(family.id).indexable);
    const versioned = products.find((p) => p.version > 1)!;
    const edits = rows<Row>("changes.jsonl", dir).filter((c) => c.entity === versioned.id && c.actor_kind !== "import")
      .map((c) => c.recorded_at!).sort();
    expect(sitemap.get(`${ORIGIN}/product/${versioned.slug}`)).toBe(edits.at(-1)!.slice(0, 10));
    const history = readFileSync(join(out, "product", versioned.slug, "history.html"), "utf-8");
    expect(history).toContain(`<link rel="canonical" href="${ORIGIN}/product/${versioned.slug}/history"`);
    const versions = JSON.parse(readFileSync(join(dir, "dist", "public", "history", `${versioned.id}.json`), "utf-8"))
      .versions.length;
    expect(history.split('<ol class="history').at(1)?.split("</ol>")[0].match(/<li\b/g)?.length).toBe(versions);
    const notFound = text(readFileSync(join(out, "404.html"), "utf-8"));
    expect(notFound).toContain(DEFAULT_MESSAGES.notFoundPage);
    expect(notFound).not.toContain("/404");
    expect(readFileSync(join(out, "product", `${versioned.slug}.html`), "utf-8"))
      .toMatch(/<table class="[^"]*\bspec-table/);
    const vendor = viewOf(versioned.id).vendor.slug;
    const listed = text(readFileSync(join(out, "vendor", `${vendor}.html`), "utf-8"));
    const names = products.filter((p) => viewOf(p.id).vendor.slug === vendor).map((p) => viewOf(p.id).name).sort();
    for (const name of names.slice(0, 3)) expect(listed).toContain(name);
    expect(readdirSync(join(out, "read-model")).sort()).toEqual(["organizations.json", "registry.json"]);
    const plain = products.find((p) => p.version === 1 && viewOf(p.id).indexable)!;
    const view = viewOf(plain.id);
    expect(sitemap.get(`${ORIGIN}/product/${plain.slug}`))
      .toBe(view.sources.map((s: Row) => s.retrieved_at!).sort().at(-1).slice(0, 10));
  }, 120_000);

  it.skipIf(!FIRESTORE
    && !process.env.MVR_EMULATOR_GATE)("writes the same bytes from the Firestore emulator as from the files", () => {
    const dir = fixture();
    const database = `t-prerender-${process.pid}`;
    const env = { ...process.env, ...MEDIA, MVR_DATA: dir, MVR_FIRESTORE_DATABASE: database };
    execFileSync("python3", ["-m", "radar", "store", "load", join(dir, "data"), "--blobs", join(dir, "blobs")],
      { cwd: DEV, env, stdio: "pipe" });
    const docs = `http://${FIRESTORE}/v1/projects/demo-mvradar/databases/${database}/documents`;
    const fromFiles = prerender({ MVR_READ_MODEL_DIR: join(dir, "dist", "public") }).out;
    const { out: fromStore, requests } = prerender({ MVR_FIRESTORE_DOCS: docs });
    const pages = JSON.parse(readFileSync(join(fromFiles, "read-model", "registry.json"), "utf-8"))
      .categories.reduce((n: number, c: { pages: number }) => n + c.pages, 0);
    const organizations = JSON.parse(readFileSync(join(fromFiles, "read-model", "organizations.json"), "utf-8")).length;
    expect(requests.filter((r) => /\/(public_products|public_organizations)\//.test(r))).toEqual([]);
    expect(requests.filter((r) => r.endsWith(":batchGet"))).toHaveLength(pages + Math.ceil(organizations / 100));
    const written = (out: string) => readdirSync(out, { recursive: true, withFileTypes: true })
      .filter((e) => e.isFile())
      .map((e) => relative(out, join(e.parentPath, e.name))).filter((f) => !f.startsWith("read-model")).sort();
    expect(written(fromStore)).toEqual(written(fromFiles));
    expect(written(fromFiles).filter((f) => !readFileSync(join(fromFiles, f)).equals(readFileSync(join(fromStore, f)))))
      .toEqual([]);
    expect(readdirSync(join(fromStore, "read-model")).sort()).toEqual(["organizations.json", "registry.json"]);

    const product = rows<Row>("products.jsonl", dir).find((p) => p.version === 1)!;
    const changeset = join(dir, "moved.json");
    writeFileSync(changeset, JSON.stringify({ changes: [{ op: "put",
      entity: { ...product, version: undefined, website_url: "https://example.com/moved" },
      reason: "The product page moved", actor_kind: "agent", actor: "link-checker", source_refs: [] }] }));
    const [event] = JSON.parse(execFileSync("python3", ["-m", "radar", "change", "apply", "--json", changeset],
      { cwd: DEV, env, encoding: "utf8" })).events;
    expect(urls(prerender({ MVR_FIRESTORE_DOCS: docs }).out).get(`${ORIGIN}/product/${product.slug}`))
      .toBe(event.recorded_at.slice(0, 10));
  }, 240_000);

  it("escapes a product and a vendor named with markup, & and U+2028 in their JSON-LD, which parses back", () => {
    const named = `</script><script>alert(1)</script> & Co\u2028\u2029`;
    const pub = join(fixture(0), "dist", "public");
    const index = JSON.parse(readFileSync(join(pub, "index.json"), "utf-8"));
    const [card] = index.products;
    const path = join(pub, "products", `${card.id}.json`);
    const view = JSON.parse(readFileSync(path, "utf-8"));
    writeFileSync(path, JSON.stringify({ ...view, name: named, vendor: { ...view.vendor, name: named } }));
    writeFileSync(join(pub, "index.json"), JSON.stringify({ ...index,
      products: index.products.map((c: { id: string }) => (c.id === card.id ? { ...c, name: named } : c)) }));
    const org = join(pub, "organizations", `${view.vendor.slug}.json`);
    writeFileSync(org, readFileSync(org, "utf-8")
      .replaceAll(JSON.stringify(view.vendor.name), JSON.stringify(named)));
    const { out } = prerender({ MVR_READ_MODEL_DIR: pub });
    const parsed: unknown[] = [];
    for (const page of [join("product", `${view.slug}.html`), join("vendor", `${view.vendor.slug}.html`)]) {
      const html = readFileSync(join(out, page), "utf-8");
      const blocks = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)];
      expect(blocks, page).toHaveLength(1);
      for (const raw of ["<", ">", "&", "\u2028", "\u2029"]) expect(blocks[0][1], page).not.toContain(raw);
      expect(html.match(/<\/script>/g)?.length, page).toBe(html.match(/<script\b/g)?.length);
      expect(JSON.stringify(JSON.parse(blocks[0][1])), page).toContain(JSON.stringify(named).slice(1, -1));
      parsed.push(JSON.parse(blocks[0][1]));
    }
    const [product, vendor] = parsed as [{ "@graph": [{ additionalProperty: { name: string }[] }] },
      { "@type": string; url: string; sameAs?: string }];
    expect(product["@graph"][0].additionalProperty.length).toBeGreaterThan(0);
    expect([vendor["@type"], vendor.url, Boolean(vendor.sameAs)])
      .toEqual(["Organization", `${ORIGIN}/vendor/${view.vendor.slug}`, true]);
  }, 120_000);

  it("streams a generated catalog of products in bounded memory, with a sitemap index", () => {
    const dir = fixture(0);
    const source = join(dir, "dist", "public");
    const pub = mkdtempSync(join(tmpdir(), "mvr-50k-"));
    cpSync(source, pub, { recursive: true });
    const registry = JSON.parse(readFileSync(join(source, "registry.json"), "utf-8"));
    const [category] = registry.categories.filter((c: { products: number }) => c.products > 0);
    const page = JSON.parse(readFileSync(join(source, "categories", category.id, "1.json"), "utf-8"));
    const view = JSON.parse(readFileSync(join(source, "products", `${page.products[0].id}.json`), "utf-8"));
    const limit = 500;
    const total = limit + 1, perPage = page.products.length, pages = Math.ceil(total / perPage);
    const id = (n: number) => `prd_${n.toString(32).padStart(10, "0")}`;
    mkdirSync(join(pub, "categories", category.id), { recursive: true });
    for (let p = 1; p <= pages; p++) {
      const cards = Array.from({ length: Math.min(perPage, total - (p - 1) * perPage) },
        (_, i) => ({ ...page.products[0], id: id((p - 1) * perPage + i), slug: `gen__${(p - 1) * perPage + i}` }));
      writeFileSync(join(pub, "categories", category.id, `${p}.json`),
        JSON.stringify({ ...page, page: p, pages, next: p < pages ? String(p + 1) : undefined, products: cards }));
      for (const card of cards) writeFileSync(join(pub, "products", `${card.id}.json`),
        JSON.stringify({ ...view, id: card.id, slug: card.slug, version: 1, models: [], family: undefined }));
    }
    writeFileSync(join(pub, "registry.json"),
      JSON.stringify({ ...registry, categories: registry.categories.map((c: { id: string }) =>
        (c.id === category.id ? { ...c, products: total, pages } : c)) }));
    const { out, rss } = prerender({ MVR_READ_MODEL_DIR: pub, MVR_SITEMAP_URLS: String(limit) }, 64);
    const index = locs(readFileSync(join(out, "sitemap.xml"), "utf-8"));
    const perFile = index.map((f) => locs(readFileSync(join(out, new URL(f).pathname), "utf-8")).length);
    expect(index).toHaveLength(2);
    expect(Math.max(...perFile)).toBeLessThanOrEqual(limit);
    expect(perFile.reduce((a, b) => a + b, 0)).toBeGreaterThan(total);
    expect(rss).toBeLessThan((768 + 128 * availableParallelism()) * 1024 * 1024);
    rmSync(pub, { recursive: true });
    rmSync(out, { recursive: true });
  }, 600_000);
});

describe("the Firestore the build reads", () => {
  // Justification (typed boundary): .firebaserc is the Firebase project file; only the default project is read.
  const project = (JSON.parse(readFileSync(join(DEV, ".firebaserc"), "utf8")) as { projects: { default: string } })
    .projects.default;

  it("is the .firebaserc project's database unless MVR_FIRESTORE_DOCS names another (the emulators')", () => {
    vi.stubEnv("MVR_FIRESTORE_DOCS", "");
    expect(resolveFirestoreDocs())
      .toBe(`https://firestore.googleapis.com/v1/projects/${project}/databases/(default)/documents`);
    vi.stubEnv("MVR_FIRESTORE_DOCS", "http://127.0.0.1:8080/v1/projects/demo-mvradar/databases/(default)/documents");
    expect(resolveFirestoreDocs())
      .toBe("http://127.0.0.1:8080/v1/projects/demo-mvradar/databases/(default)/documents");
    vi.unstubAllEnvs();
  });
});
