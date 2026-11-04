import fs from "node:fs";
import path from "node:path";
import { BRAND_CONFIG } from "../src/ui/theme/brand.ts";
import { type PageHeadMeta, headMetaTags, serializeJsonLd } from "../src/shell/seo/seo.ts";
import type { CatalogRepository } from "../src/domain/ports/CatalogRepository.ts";
import { FilesCatalogRepository } from "../src/adapters/read-model/files.ts";
import { FirestoreCatalogRepository } from "../src/adapters/read-model/firestore.ts";

export const DEV = path.resolve(import.meta.dirname, "../..");
export const DATA = path.resolve(DEV, process.env.MVR_DATA || "data");

function firebaseProject(): string {
  const rcPath = path.join(DEV, ".firebaserc");
  // Justification (typed boundary): .firebaserc is the Firebase project file; only the default project is read.
  const rc = (fs.existsSync(rcPath) ? JSON.parse(fs.readFileSync(rcPath, "utf-8"))
    : {}) as { projects?: { default?: string } };
  const project = (rc.projects?.default || "").trim();
  if (!project) throw new Error("no default project in .firebaserc");
  return project;
}

export function resolveSiteOrigin(): string {
  const envUrl = (process.env.MVR_SITE_URL || "").trim().replace(/\/+$/, "");
  return envUrl || `https://${firebaseProject()}.web.app`;
}

export function resolveFirestoreDocs(): string {
  return process.env.MVR_FIRESTORE_DOCS
    || `https://firestore.googleapis.com/v1/projects/${firebaseProject()}/databases/(default)/documents`;
}

const ENTITIES: Readonly<Record<string, string>> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
  "'": "&#039;" };

export function readModel(): CatalogRepository {
  const dir = process.env.MVR_READ_MODEL_DIR;
  return dir ? filesReadModel(dir) : new FirestoreCatalogRepository(resolveFirestoreDocs());
}

export const filesReadModel = (dir: string): CatalogRepository => new FilesCatalogRepository(async (file) => {
  const full = path.join(dir, decodeURIComponent(file));
  return fs.existsSync(full) ? JSON.parse(fs.readFileSync(full, "utf-8")) : null;
});

export const escapeHtml = (str: string): string => str.replace(/[&<>"']/g, (c) => ENTITIES[c]);

const stripped = (template: string, title: string, metas: RegExp): string =>
  template.replace(/<title>.*?<\/title>/i, `<title>${escapeHtml(title)}</title>`)
    .replace(/<link\s+rel="canonical"[^>]*>/gi, "").replace(metas, "");

const withTags = (html: string, tags: readonly string[]): string =>
  html.replace("</head>", `  ${tags.join("\n  ")}\n</head>`);

export function renderHead(template: string, head: PageHeadMeta): string {
  return withTags(stripped(template, head.title,
    /<meta\s+(property|name)="(og:[^"]+|twitter:[^"]+|description|robots)"[^>]*>/gi), [
    ...(head.noindex ? [`<meta name="robots" content="noindex" />`] : []),
    `<link rel="canonical" href="${escapeHtml(head.canonicalUrl)}" />`,
    ...headMetaTags(head).map(([attr, key, content]) => `<meta ${attr}="${key}" content="${escapeHtml(content)}" />`),
    `<script type="application/ld+json">${serializeJsonLd(head.jsonLd)}</script>`,
  ]);
}

export function renderNotFoundHead(template: string, title: string, description: string): string {
  const html = stripped(template, title, /<meta\s+(property|name)="(og:[^"]+|twitter:[^"]+|description)"[^>]*>/gi)
    .replace(/<script\s+type="application\/ld\+json"[^>]*>[\s\S]*?<\/script>/gi, "");
  return withTags(html, [
    `<meta name="robots" content="noindex" />`,
    `<meta name="description" content="${escapeHtml(description)}" />`,
    `<meta property="og:title" content="${escapeHtml(title)}" />`,
    `<meta property="og:description" content="${escapeHtml(description)}" />`,
    `<meta property="og:type" content="website" />`,
    `<meta property="og:site_name" content="${escapeHtml(BRAND_CONFIG.wordmark)}" />`,
    `<meta name="twitter:card" content="summary" />`,
    `<meta name="twitter:title" content="${escapeHtml(title)}" />`,
    `<meta name="twitter:description" content="${escapeHtml(description)}" />`,
  ]);
}
