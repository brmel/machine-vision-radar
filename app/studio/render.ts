import fs from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { studioWebpack } from "../remotion.config.ts";
import { readModel, resolveSiteOrigin } from "../scripts/head.ts";
import type { CatalogRepository } from "../src/domain/ports/CatalogRepository.ts";
import { logger } from "../src/shell/logger.ts";
import { termLabel } from "../src/ui/specs/specFormat.ts";
import { productPath } from "../src/domain/paths.ts";
import { DEFAULT_LANGUAGE } from "../src/domain/languages.ts";
import { bannedIn, parseScript, shown, srt, unheld, type ClipScript } from "./clips/script.ts";
import type { ClipProps } from "./clips/Clip.tsx";
import type { CatalogCardProps } from "./cards/CatalogCard.tsx";
import type { ProductCardProps } from "./cards/ProductCard.tsx";
import { facts, TEMPLATES, type Card, type Post, type Template } from "./clips/templates.ts";
import { record } from "./footage/record.ts";
import { CLIP_SIZES, SIZES } from "./sizes.ts";

const APP = path.resolve(import.meta.dirname, "..");
const OUT = process.env.MVR_STUDIO_OUT ?? path.join(APP, "studio", "out");
const browserExecutable = chromium.executablePath();
const host = (): string => new URL(resolveSiteOrigin()).host;

async function props(repo: CatalogRepository, card: Card): Promise<(rows: number) => CatalogCardProps
  | ProductCardProps> {
  const registry = await repo.registry();
  const stamp = { asOf: registry.data_as_of ?? null };
  if (card.kind === "catalog") return () => ({ ...stamp, address: host(), counts: registry.counts });
  const { product } = card;
  const cells = product.core.filter((c) => c.value !== undefined);
  return (rows) => ({
    ...stamp, address: `${host()}${productPath(product.slug)}`, name: product.name,
    category: termLabel(registry.categories, product.category, DEFAULT_LANGUAGE.code), vendor: product.vendor.name,
    cells: cells.slice(0, rows), sources: product.sources, specDefs: registry.spec_definitions,
  });
}

async function bundled(folder: string): Promise<string> {
  fs.mkdirSync(folder, { recursive: true });
  fs.copyFileSync(path.join(APP, "public", "favicon.svg"), path.join(folder, "favicon.svg"));
  return bundle({ entryPoint: path.join(APP, "studio", "index.ts"), publicDir: folder,
    webpackOverride: studioWebpack });
}

async function draw(repo: CatalogRepository, card: Card, folder: string): Promise<void> {
  const drawn = await props(repo, card);
  const serveUrl = await bundled(folder);
  for (const size of SIZES) {
    const inputProps = drawn(size.rows);
    const composition =
      await selectComposition({ serveUrl, id: `${card.kind}-${size.name}`, inputProps, browserExecutable });
    const output = path.join(folder, `card-${size.width}x${size.height}.png`);
    await renderStill({ composition, serveUrl, output, inputProps, browserExecutable });
    fs.writeFileSync(path.join(folder, `card-${size.width}x${size.height}.json`),
      `${JSON.stringify(inputProps, null, 2)}\n`);
    logger.info(`studio: wrote ${path.relative(APP, output)}`);
  }
}

async function filled(name: string | undefined, id: string | undefined): Promise<{ repo: CatalogRepository; post: Post;
  folder: string }> {
  const template: Template | undefined = Object.entries(TEMPLATES).find(([n]) => n === name)?.[1];
  if (!template) throw new Error(`studio: a template is one of ${Object.keys(TEMPLATES).join(", ")}`);
  const repo = readModel();
  const made = await template(repo, id);
  return { repo, post: made, folder: path.join(OUT, made.name) };
}

async function make(name: string | undefined, id: string | undefined, base: string | undefined): Promise<void> {
  if (!base || !URL.canParse(base)) throw new Error("studio: --base takes the site's origin, as http://127.0.0.1:4173");
  const { repo, post: made, folder } = await filled(name, id);
  fs.mkdirSync(folder, { recursive: true });
  await record(made.steps, folder, base);
  if (made.card) await draw(repo, made.card, folder);
  fs.writeFileSync(path.join(folder, "script.json"), `${JSON.stringify(made.script, null, 2)}\n`);
  logger.info(`studio: wrote ${path.relative(APP, folder)}: its footage${made.card ? ", its card"
    : ""} and script.json`);
}

async function still(name: string | undefined, id: string | undefined): Promise<void> {
  const { repo, post: made, folder } = await filled(name, id);
  if (!made.card) throw new Error(`studio: the ${name} template draws no card`);
  await draw(repo, made.card, folder);
}

function fileOf(folder: string, shows: ClipScript["segments"][number]["shows"],
    sizes: readonly string[]): ClipProps["files"][number] {
  const name = sizes.map((size) => `${shows}-${size}`)
    .find((n) => fs.existsSync(path.join(folder, `${n}.${shows === "footage" ? "webm" : "png"}`)));
  if (!name) throw new Error(`studio: ${folder} holds no ${shows} at ${sizes.join(" or ")}: make its post first`);
  if (shows === "card") return { file: `${name}.png`, lead: 0 };
  return { file: `${name}.webm`,
    lead: Number(JSON.parse(fs.readFileSync(path.join(folder, `${name}.json`), "utf-8")).lead) };
}

const scriptIn = (folder: string): ClipScript =>
  parseScript(JSON.parse(fs.readFileSync(path.join(folder, "script.json"), "utf-8")));

async function check(folder: string | undefined): Promise<void> {
  if (!folder) throw new Error("studio: a check reads a post's folder, `check <post folder>`");
  const text = fs.readFileSync(path.join(folder, "post.md"), "utf-8");
  const held = await facts(readModel(), scriptIn(folder).about);
  const findings =
    [...bannedIn(text), ...unheld(text, held).map((f) => `${f}: no record the post is about holds this figure`)];
  for (const f of findings) logger.warn(`studio: post.md says ${f}`);
  if (findings.length > 0) throw new Error(`studio: post.md has ${findings.length} finding(s)`);
  logger.info("studio: post.md passes the brand's checks");
}

async function clip(folder: string | undefined, only: string | undefined): Promise<void> {
  if (!folder) throw new Error("studio: a clip renders a post's folder, `clip <post folder>`");
  if (only && !CLIP_SIZES.some((s) => s.name === only))
    throw new Error(`studio: a clip's size is one of ${CLIP_SIZES.map((s) => s.name).join(", ")}`);
  const script = scriptIn(folder);
  const repo = readModel();
  const unknown = unheld(shown(script), await facts(repo, script.about));
  if (unknown.length > 0)
    throw new Error(`studio: the script states ${unknown.join(", ")}, which no record it is about holds`);
  const registry = await repo.registry();
  const stamp = { address: host(), asOf: registry.data_as_of ?? null };
  const serveUrl = await bundled(folder);
  for (const size of CLIP_SIZES.filter((s) => !only || s.name === only)) {
    const inputProps = { ...stamp, ...script,
      files: script.segments.map((s) => fileOf(folder, s.shows, size.footage)) };
    const composition = await selectComposition({ serveUrl, id: `clip-${size.name}`, inputProps, browserExecutable });
    const output = path.join(folder, `clip-${size.width}x${size.height}.mp4`);
    await renderMedia({ composition, serveUrl, codec: "h264", outputLocation: output, inputProps, browserExecutable });
    fs.writeFileSync(path.join(folder, `clip-${size.width}x${size.height}.srt`), srt(script));
    fs.writeFileSync(path.join(folder, `clip-${size.width}x${size.height}.json`),
      `${JSON.stringify(inputProps, null, 2)}\n`);
    logger.info(`studio: wrote ${path.relative(APP, output)}`);
  }
}

async function main(): Promise<void> {
  const [command, ...rest] = process.argv.slice(2);
  const at = rest.indexOf("--base");
  const [first, second] = at < 0 ? rest : rest.slice(0, at);
  if (command === "make") return make(first, second, at < 0 ? resolveSiteOrigin() : rest[at + 1]);
  if (command === "still") return still(first, second);
  if (command === "clip") return clip(first, second);
  if (command === "check") return check(first);
  throw new Error("studio: a command is make, still, clip or check");
}

main().catch((err: unknown) => {
  logger.error("studio: stopped", {}, err);
  process.exit(1);
});
