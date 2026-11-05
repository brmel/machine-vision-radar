import fs from "node:fs";
import path from "node:path";
import { type PageHeadMeta, serializeJsonLd } from "../../src/shell/seo/seo.ts";
import type { Route } from "../../src/shell/routing/routes.ts";
import type { Start } from "../../src/shell/root/start.ts";
import type { CatalogRepository } from "../../src/domain/ports/CatalogRepository.ts";
import type { ProductView, RegistryView } from "../../src/domain/views.ts";
import { readModel, renderHead, resolveSiteOrigin } from "../head.ts";

const SERVER = path.resolve(import.meta.dirname, "../../dist-server/server.js");
export const DIST_DIR =
  path.resolve(process.env.MVR_PRERENDER_OUT ?? path.resolve(import.meta.dirname, "../../dist"));

export const ROOT = '<div id="root"></div>';

export interface Site {
  readonly repo: CatalogRepository;
  readonly registry: RegistryView;
  readonly template: string;
  readonly base: string;
  readonly render: (route: Route) => Promise<string>;
}

export function write(file: string, text: string): void {
  const at = path.join(DIST_DIR, file);
  fs.mkdirSync(path.dirname(at), { recursive: true });
  fs.writeFileSync(at, text, "utf-8");
}

export function writePage(site: Site, file: string, head: PageHeadMeta, body: string, embedded?: ProductView): void {
  const html = renderHead(site.template, head).replace(ROOT, () => `<div id="root">${body}</div>`);
  write(file, embedded ? html.replace("</body>",
    () => `<script type="application/json" id="mvr-product">${serializeJsonLd(embedded)}</script>\n</body>`) : html);
}

async function renderer(repo: CatalogRepository): Promise<Site["render"]> {
  if (!fs.existsSync(SERVER)) throw new Error(`prerender: no ${SERVER}; run npm run build:server first`);
  // Justification (typed boundary): dist-server/server.js is src/shell/root/server.tsx as vite build --ssr writes it.
  const { renderPage } = (await import(SERVER)) as typeof import("../../src/shell/root/server.tsx");
  return (route) => {
    const start: Start = { route, preferred: [], theme: "system", compared: [], prerendered: null };
    return renderPage(start, repo);
  };
}

export async function openSite(template: string): Promise<Site> {
  const repo = readModel();
  return { repo, registry: await repo.registry(), template, base: resolveSiteOrigin(), render: await renderer(repo) };
}
