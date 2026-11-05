import { useEffect } from "react";
import { BRAND_CONFIG } from "../../ui/theme/brand.ts";
import { type PageHeadMeta, headMetaTags, serializeJsonLd } from "./seo.ts";

function headElement(tag: "meta" | "link" | "script", name: string, value: string): HTMLElement {
  const found = document.head.querySelector<HTMLElement>(`${tag}[${name}="${value}"]`);
  if (found) return found;
  const added = document.createElement(tag);
  added.setAttribute(name, value);
  return document.head.appendChild(added);
}

function upsertMeta(attr: "name" | "property", key: string, content: string): void {
  headElement("meta", attr, key).setAttribute("content", content);
}

export function setCanonical(url: string): void {
  headElement("link", "rel", "canonical").setAttribute("href", url);
}

export function syncDocumentHead(meta: PageHeadMeta): void {
  document.title = meta.title;
  if (meta.noindex) upsertMeta("name", "robots", "noindex");
  else document.querySelector('meta[name="robots"]')?.remove();

  setCanonical(meta.canonicalUrl);
  for (const [attr, key, content] of headMetaTags(meta)) upsertMeta(attr, key, content);
  headElement("script", "type", "application/ld+json").textContent = serializeJsonLd(meta.jsonLd);
}

export function syncNotFoundHead(title: string): void {
  document.title = `${title} · ${BRAND_CONFIG.wordmark}`;
  upsertMeta("name", "robots", "noindex");
  document.querySelector('link[rel="canonical"]')?.remove();
  document.head.querySelector('script[type="application/ld+json"]')?.remove();
}

export function useRecordHead(head: PageHeadMeta | null, loaded = false, missing = ""): void {
  useEffect(() => {
    if (head) syncDocumentHead(head);
    else if (loaded) syncNotFoundHead(missing);
  }, [head, loaded, missing]);
}
