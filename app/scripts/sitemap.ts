import fs from "node:fs";
import path from "node:path";
import type { HistoryView, ProductView } from "../src/domain/views.ts";
import { escapeHtml } from "./head.ts";

const SITEMAP_URLS = Number(process.env.MVR_SITEMAP_URLS || 50_000);

interface SitemapEntry {
  readonly path: string;
  readonly lastmod?: string;
}

export function lastmod(view: ProductView, history: HistoryView | null): string | undefined {
  const edits = (history?.versions ?? []).filter((v) => v.actor_kind !== "import").map((v) => v.recorded_at);
  const dates = edits.length > 0 ? edits : view.sources.map((s) => s.retrieved_at);
  return dates.sort().at(-1)?.slice(0, 10);
}

export class Sitemap {
  private readonly dir: string;
  private readonly origin: string;
  private readonly files: string[] = [];
  private urls: string[] = [];

  constructor(dir: string, origin: string) {
    this.dir = dir;
    this.origin = origin;
  }

  add(entry: SitemapEntry): void {
    this.urls.push(`  <url>\n    <loc>${escapeHtml(this.origin + entry.path)}</loc>\n${entry.lastmod
      ? `    <lastmod>${entry.lastmod}</lastmod>\n` : ""}  </url>`);
    if (this.urls.length === SITEMAP_URLS) this.flush();
  }

  private flush(): void {
    const name = `sitemap-${this.files.length + 1}.xml`;
    fs.writeFileSync(path.join(this.dir, name),
      `<?xml version="1.0" encoding="UTF-8"?>\n<urlset `
        + `xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${this.urls.join("\n")}\n</urlset>\n`, "utf-8");
    this.files.push(name);
    this.urls = [];
  }

  close(): string[] {
    if (this.urls.length > 0 || this.files.length === 0) this.flush();
    const index = this.files
      .map((f) => `  <sitemap>\n    <loc>${escapeHtml(`${this.origin}/${f}`)}</loc>\n  </sitemap>`).join("\n");
    fs.writeFileSync(path.join(this.dir, "sitemap.xml"),
      `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex `
        + `xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${index}\n</sitemapindex>\n`, "utf-8");
    return this.files;
  }
}

export function robots(origin: string): string {
  return `User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /administrator\n\nSitemap: ${origin}/sitemap.xml\n`;
}
