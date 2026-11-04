import fs from "node:fs";
import path from "node:path";
import { logger } from "../src/shell/logger.ts";
import { DATA, DEV } from "./head.ts";
import { STATIC_ROUTES } from "../src/shell/routing/router.ts";

// Justification (typed boundary): app/perf-budgets.json holds every performance budget; only this one is read here.
const MAX_BUNDLE_KIB =
  (JSON.parse(fs.readFileSync(new URL("../perf-budgets.json", import.meta.url),
    "utf-8")) as { first_load_js_kib: number }).first_load_js_kib;
const ADMIN_MARKER = "signInWithPopup";

export interface BuildGuardOptions {
  repoRoot?: string;
  dataRoot?: string;
  adminEnabled?: boolean;
  maxBundleKiB?: number;
  denyList?: string;
}

function read(file: string, label: string): string {
  if (!fs.existsSync(file)) throw new Error(`build guard: missing ${label} at ${file}`);
  return fs.readFileSync(file, "utf-8");
}

function checkAdminCode(assetsDir: string, jsFiles: readonly string[], mainBundle: string,
    adminEnabled: boolean): void {
  for (const file of jsFiles) {
    const content = fs.readFileSync(path.join(assetsDir, file), "utf-8");
    if ((file.startsWith("AdminSection-") || content.includes(ADMIN_MARKER)) && (!adminEnabled || file === mainBundle))
      throw new Error(`build guard: ${file} ships admin code ${adminEnabled ? "in the main bundle"
        : "with VITE_ENABLE_ADMIN off"}`);
  }
  if (adminEnabled && !jsFiles.some((f) => f.startsWith("AdminSection-")))
    throw new Error("build guard: VITE_ENABLE_ADMIN is on, yet no lazy AdminSection chunk was built");
}

export function runBuildGuards(options: BuildGuardOptions = {}): string {
  const repoRoot = options.repoRoot ?? DEV;
  const adminEnabled = options.adminEnabled ?? process.env.VITE_ENABLE_ADMIN === "true";
  const maxKiB = options.maxBundleKiB ?? MAX_BUNDLE_KIB;

  const assetsDir = path.join(repoRoot, "app/dist/assets");
  if (!fs.existsSync(assetsDir)) throw new Error(`build guard: assets directory missing at ${assetsDir}`);
  const jsFiles = fs.readdirSync(assetsDir).filter((f) => f.endsWith(".js"));
  const indexFiles = jsFiles.filter((f) => f.startsWith("index-"));
  if (indexFiles.length !== 1)
    throw new Error(`build guard: expected exactly one dist/assets/index-*.js, found ${indexFiles.length}`);

  const mainBundle = indexFiles[0];
  checkAdminCode(assetsDir, jsFiles, mainBundle, adminEnabled);

  const sizeKiB = fs.statSync(path.join(assetsDir, mainBundle)).size / 1024;
  if (sizeKiB > maxKiB)
    throw new Error(`build guard: main bundle ${mainBundle} is ${sizeKiB.toFixed(1)} KiB, exceeds budget of ${maxKiB} `
      + `KiB`);

  const distDir = path.join(repoRoot, "app/dist");
  checkHtmlPrerender(distDir, options.dataRoot ?? DATA);
  checkNews(distDir);
  const denied = checkPublicFiles(repoRoot, options.denyList);

  const admin = adminEnabled ? "admin in its lazy chunks only" : "no admin";
  return `build guard: OK (${admin}; main bundle ${mainBundle} ${sizeKiB.toFixed(1)} KiB of ${maxKiB} KiB; `
    + `verified prerender HTML; ${denied})`;
}

const HOSTING_ADDRESS = /[\w.+-]+@[\w-]+\.(?:web\.app|firebaseapp\.com)\b/i;
const PUBLIC_TEXT = /\.(?:html|js|json|txt|xml|atom|svg|md)$/;

function denyList(file: string | undefined): RegExp[] | null {
  if (!file) return null;
  return read(file, "deny list").split("\n").map((line) => line.trim()).filter(Boolean)
    .map((name) =>
      new RegExp(`(?<![\\p{L}\\p{N}])${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\p{L}\\p{N}])`, "iu"));
}

function checkPublicFiles(repoRoot: string, file = process.env.MVR_DENY_LIST): string {
  const names = denyList(file);
  checkPublicText([path.join(repoRoot, "app/dist"), path.join(repoRoot, "docs")], names ?? []);
  return names ? `no name of the deny list's ${names.length}`
    : "personal names unchecked: MVR_DENY_LIST names no deny list";
}

function checkPublicText(dirs: readonly string[], names: readonly RegExp[]): void {
  for (const dir of dirs) {
    for (const file of fs.readdirSync(dir, { recursive: true, encoding: "utf8" }).filter((f) => PUBLIC_TEXT.test(f))) {
      const text = fs.readFileSync(path.join(dir, file), "utf-8");
      const address = HOSTING_ADDRESS.exec(text)?.[0];
      if (address)
        throw new Error(`build guard: ${path.join(dir,
          file)} gives ${address}, at a hosting domain that receives no mail`);
      const found = names.findIndex((name) => name.test(text));
      if (found >= 0)
        throw new Error(`build guard: ${path.join(dir, file)} carries name ${found + 1} of the deny list`);
    }
  }
}

const NOT_PUBLIC = "admin.html";
const SITE_PAGES = new Set<string>(["index.html", ...STATIC_ROUTES.map((r) => r.file)]);
const FLOOR = 200;
const SHORT: Readonly<Record<string, string>> = { "compare.html": "empty until the reader picks products, and the "
  + "picks stay in their browser" };

const visibleText = (html: string): string => html
  .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "")
  .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, "")
  .replace(/<[^>]+>/g, " ")
  .replace(/&[a-z0-9]+;/gi, " ")
  .replace(/&#[0-9]+;/gi, " ");

function checkBody(file: string, content: string, where: string): void {
  const body = content.split(/<body\b[^>]*>/i)[1] ?? content;
  const headings = body.match(/<h1\b/gi)?.length ?? 0;
  if (headings !== 1)
    throw new Error(`build guard: ${where} has ${headings} h1 headings in its body; a public page has one`);
  const main = body.split(/<main\b[^>]*>/i)[1]?.split(/<\/main>/i)[0] ?? "";
  const shown = visibleText(main).replace(/\s+/g, " ").trim().length;
  if (SITE_PAGES.has(file) && !(file in SHORT) && shown < FLOOR) {
    throw new Error(`build guard: ${where} shows ${shown} characters; a page of the site's own words shows at least `
      + `${FLOOR}`);
  }
}

const SNAKE_CASE_REGEX = /\b[a-z0-9]+(?:_[a-z0-9]+)+\b/g;
const LOG = "/history.html";
const CHANGE_LOG = /<ol class="history[\s\S]*?<\/ol>/;
const ALLOWED_PREFIXES = ["prd_", "org_", "src_", "clm_"];

function checkSpecTables(content: string, rawSnakeKeys: ReadonlySet<string>, where: string): void {
  for (const [, table] of content.matchAll(/<table[^>]*class="[^"]*spec-table[^"]*"[^>]*>([\s\S]*?)<\/table>/g)) {
    for (const [, cell] of table.matchAll(/<tr[^>]*>[\s\S]*?<td[^>]*>([^<]+)<\/td>/g)) {
      if (rawSnakeKeys.has(cell.trim()))
        throw new Error(`build guard: raw spec key '${cell.trim()}' used as spec-table label in ${where}`);
    }
  }
}

export function checkHtmlPrerender(distDir: string, dataRoot: string): void {
  const htmlFiles = fs.readdirSync(distDir, { recursive: true, encoding: "utf8" })
    .filter((name) => name.endsWith(".html")).map((name) => path.join(distDir, name));
  if (htmlFiles.length === 0) return;

  const specDefsPath = path.join(dataRoot, "registry", "spec_definitions.json");
  // Justification (typed boundary): registry file parsed once; only `id` is read.
  const defs = JSON.parse(read(specDefsPath, "spec definitions")) as Array<{ id: string }>;
  const rawSnakeKeys = new Set(defs.map((d) => d.id).filter((id) => id.includes("_")));

  for (const file of htmlFiles) {
    const content = fs.readFileSync(file, "utf-8");
    const where = path.relative(distDir, file);

    if (content.includes("[object Object]"))
      throw new Error(`build guard: prerendered HTML contains [object Object] in ${where}`);

    checkSpecTables(content, rawSnakeKeys, where);

    const name = path.relative(distDir, file);
    const matches = visibleText(name.endsWith(LOG) ? content.replace(CHANGE_LOG, "") : content)
      .match(SNAKE_CASE_REGEX) || [];
    const bad = matches.filter((m) => !ALLOWED_PREFIXES.some((p) => m.startsWith(p)));
    if (bad.length > 0) throw new Error(`build guard: visible snake_case found in ${where}: ${bad.join(", ")}`);
    if (name !== NOT_PUBLIC) checkBody(name, content, where);
  }
}

const slugOf = (url: string): string => decodeURIComponent(url.split("/news/")[1] ?? "");

export function checkNews(distDir: string): void {
  const dir = path.join(distDir, "news");
  // Justification (typed boundary): the JSON Feed the prerender wrote; only each item's address and date are read.
  const items = (JSON.parse(read(path.join(dir, "feed.json"), "news/feed.json")) as { items: { url: string;
    date_published?: string }[] }).items;
  const entries = read(path.join(dir, "feed.atom"), "news/feed.atom").split("<entry>").slice(1)
    .map((entry) => ({ url: entry.split("<id>")[1]?.split("</id>")[0] ?? "",
      date_published: entry.split("<published>")[1]?.split("</published>")[0] }));
  const pages = new Set(fs.readdirSync(dir).filter((f) => f.endsWith(".html")).map((f) => f.slice(0, -".html".length)));
  for (const slug of pages) {
    if (!read(path.join(dir, `${slug}.html`), `news/${slug}.html`).includes('"datePublished":"'))
      throw new Error(`build guard: news/${slug}.html has no publication date`);
  }
  for (const item of [...items, ...entries]) {
    if (!item.date_published || !pages.has(slugOf(item.url)))
      throw new Error(`build guard: a feed carries ${item.url}, which is no published article's page`);
  }
}

if (process.argv[1] && import.meta.filename === fs.realpathSync(process.argv[1])) {
  try {
    logger.info(runBuildGuards());
  } catch (err) {
    logger.error("the build guards failed", {}, err);
    process.exit(1);
  }
}
