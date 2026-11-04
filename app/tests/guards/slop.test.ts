import { execFileSync } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";
import { DATA } from "../../scripts/head.ts";
import { describe, expect, it } from "vitest";
import { bannedClaims, bannedPhrases } from "../../studio/clips/script.ts";
import { DEFAULT_LANGUAGE } from "../../src/domain/languages.ts";
import { MESSAGES } from "../../src/shell/i18n/index.tsx";
import { APP, type AstNode, filesUnder, findings, isNode, lines } from "./source.ts";

type Banned = { pattern: string; reason: string };
// Justification (typed boundary): the data's banned words, which the validator parses into typed lists.
const filler = JSON.parse(readFileSync(join(DATA, "no_filler.json"), "utf8")) as Record<
  "placeholders" | "anywhere" | "copy" | "headings" | "claims", Banned[]>;
const HEADINGS = filler.headings.map((b) => new RegExp(`^(?:${b.pattern})$`, "iu"));
const PICTOGRAPH = /(?![©®™])[\p{Extended_Pictographic}←-⇿✀-➿⟰-⟿⤀-⥿⬀-⯿]/u;

function wordFindings(text: string): string[] {
  const phrases = bannedPhrases(text);
  const glyph = text.match(PICTOGRAPH)?.[0];
  const dashes = text.split("—").length - 1;
  return [...phrases, ...(glyph ? [`pictograph ${glyph}`] : []),
    ...(dashes >= 3 && text.split(/\s+/).length < 600 ? [`${dashes} em dashes`] : [])];
}

const headingFindings = (heading: string): string[] =>
  (HEADINGS.some((re) => re.test(heading.trim())) ? [`template heading "${heading.trim()}"`] : []);

const TOKENS = join("src", "ui", "theme", "tokens.css");
const PALETTE = "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo"
  + "|violet|purple|fuchsia|pink|rose";
const UTILITY = "text|bg|border|divide|ring|outline|fill|stroke|accent|from|to|via|shadow|decoration|caret";
const STOCK = "unsplash\\.com|pexels\\.com|picsum\\.photos|pravatar\\.cc|placehold\\.co|placeholder\\.com"
  + "|randomuser\\.me|ui-avatars\\.com";
const MARKUP: readonly (readonly [string, RegExp])[] = [
  ["raw colour", /(?<![\w&])#(?=[0-9a-f]*[a-f])[0-9a-f]{3,8}\b|(?<![\w&])#[0-9]{6}\b/i],
  ["raw colour", /\b(?:rgba?|hsla?|oklch|oklab|hwb|lab|lch)\(/],
  ["palette colour", new RegExp(`(?<![a-z])(?:${PALETTE})-\\d{2,3}\\b`)],
  ["palette colour", new RegExp(`(?<![\\w-])(?:[\\w-]+:)*(?:${UTILITY})-(?:white|black)\\b`)],
  ["bold weight", /\bfont-(?:bold|extrabold|black)\b/],
  ["gradient text", /\bbg-clip-text\b|\bbg-(?:gradient|linear|radial|conic)-/],
  ["blurred orb", /\bblur-(?:2xl|3xl|\[)/],
  ["stock image", new RegExp(`\\b(?:${STOCK})\\b`)],
];
const frosted = (text: string): number => text.match(/\bbackdrop-blur\b/g)?.length ?? 0;

const markupFindings = (source: string): string[] =>
  source.split("\n")
    .flatMap((line, i) => MARKUP.filter(([, re]) => re.test(line)).map(([tell]) => `${i + 1}: ${tell}`));

function shown(node: AstNode): string {
  if (node.type === "JSXText" || (node.type === "Literal" && typeof node.value === "string")) return String(node.value);
  return node.type === "TemplateElement" && isNode(node.value) ? String(node.value.cooked ?? "") : "";
}

const visible = (html: string): string => html.replace(/<(script|style)\b[\s\S]*?<\/\1>/gi, " ")
  .replace(/<[^>]+>/g, " ")
  .replace(/&#0*39;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&")
  .replace(/\s+/g, " ");

function pageFindings(html: string): string[] {
  const body = html.split(/<body\b[^>]*>/i)[1] ?? html;
  const headings =
    [...body.matchAll(/<h[1-6]\b[^>]*>([\s\S]*?)<\/h[1-6]>/gi)].flatMap(([, inner]) => headingFindings(visible(inner)));
  return [...wordFindings(visible(body)), ...bannedClaims(visible(body), DEFAULT_LANGUAGE.code), ...headings,
    ...markupFindings(body).map((f) => f.split(": ")[1]), ...(frosted(body) > 1 ? ["frosted element"] : [])];
}

function registryTexts(): [string, string][] {
  const texts = (value: unknown): [string, string][] => {
    if (Array.isArray(value)) return value.flatMap(texts);
    if (typeof value !== "object" || value === null) return [];
    const localized = "en" in value && typeof value.en === "string";
    return localized ? Object.entries(value).filter((e): e is [string, string] => typeof e[1] === "string")
      : Object.values(value).flatMap(texts);
  };
  const root = join(DATA, "registry");
  return filesUnder([root], /\.json$/).flatMap((path) => texts(JSON.parse(readFileSync(join(APP, path), "utf8"))));
}

describe("slop", () => {
  it("keeps each list of the contract sorted, every pattern with its reason", () => {
    const lists: readonly (readonly { pattern: string; reason: string }[])[] =
      [filler.placeholders, filler.anywhere, filler.copy, filler.headings, filler.claims];
    for (const list of lists) {
      expect(list.map((b) => b.pattern)).toEqual(list.map((b) => b.pattern).sort());
      expect(list.filter((b) => !b.reason)).toEqual([]);
    }
  });

  it("fires on each tell, not on plain words, legal marks or issue numbers", () => {
    expect(wordFindings("Elevate your workflow with a best-in-class 10x lens, our source-of-truth"))
      .toEqual(['"best-in-class": a superlative no source states',
        '"source-of-truth": a slogan about the radar, not a fact', '"Elevate": hero cliché']);
    expect(wordFindings("Datasheet ↗")).toEqual(["pictograph ↗"]);
    expect([...bannedClaims("Every value verified, none stale", "en"), ...bannedClaims("Valeurs vérifiées", "fr"),
      ...bannedClaims("unverified", "en"), ...bannedClaims("Northwind Instruments", "en")])
      .toEqual(['"stale": a value is dated by its source, never judged',
        '"verified": the radar compiles public sources, it verifies nothing',
        '"vérifiées": the radar compiles public sources, it verifies nothing']);
    expect(wordFindings("🚀 Fast setup")).toEqual(["pictograph 🚀"]);
    expect(wordFindings("One — two — three — four")).toEqual(["3 em dashes"]);
    expect(wordFindings("A 5 MP camera® — one dash, 12 fps, a Fourier transform.")).toEqual([]);
    expect(pageFindings("<body><h1>Ready</h1><p>In today&#039;s plants</p></body>"))
      .toEqual(['"In today\'s": AI-template opener']);
    expect([...headingFindings("How it works"), ...headingFindings("Why choose us"),
      ...headingFindings("How it works with GigE")])
      .toEqual(['template heading "How it works"', 'template heading "Why choose us"']);
    const fixture = [
      'const a = "text-neutral-600";', 'const b = "hover:bg-white";', "const c = { color: '#ffd21e' };",
      'const d = "fill-[rgb(0,0,0)]";', '<h1 className="text-title font-bold">',
      '<span className="bg-gradient-to-r bg-clip-text text-transparent">', '<div className="absolute blur-3xl">',
      '<img src="https://images.unsplash.com/photo-1">',
      'const e = "bg-surface text-muted font-heading"; // #138, &#039;',
    ].join("\n");
    expect(markupFindings(fixture)).toEqual(["1: palette colour", "2: palette colour", "3: raw colour", "4: raw colour",
      "5: bold weight", "6: gradient text", "7: blurred orb", "8: stock image"]);
    expect(pageFindings('<body><header class="backdrop-blur-md"></header><nav '
      + 'class="backdrop-blur-sm"></nav><h2>Features</h2><p>Unlock 10x faster checks.</p></body>')).toEqual([
      '"10x faster": a multiplier with no measure behind it (a lens\'s 10x is a magnification)',
      '"Unlock": hero cliché', 'template heading "Features"', "frosted element"]);
    expect(lines("x.tsx", 'const x = <p title="a ↗">{n} → {m}</p>;', (node) => PICTOGRAPH.test(shown(node))))
      .toEqual([1, 1]);
  });

  it("finds none in the site's own words", () => {
    const messages = Object.entries(MESSAGES).flatMap(([code, strings]) =>
      Object.entries(strings).flatMap(([key, text]) => [...wordFindings(text), ...headingFindings(text),
        ...bannedClaims(text, code)].map((f) => `${code}.${key}: ${f}`)));
    const brand = wordFindings(readFileSync(join(APP, "..", "docs", "BRAND.md"), "utf8")).map((f) => `BRAND.md: ${f}`);
    const registry = registryTexts().flatMap(([code, text]) =>
      [...wordFindings(text), ...bannedClaims(text, code)].map((f) => `registry "${text}": ${f}`));
    expect([...messages, ...brand, ...registry]).toEqual([]);
  });

  it("names no search engine's inner workings on a public page: the AI mark says it", () => {
    const root = join(APP, "src", "shell", "i18n", "messages");
    const strings = (code: string, file: string): [string, string][] =>
      // Justification (typed boundary): a messages file is one object of strings.
      Object.entries(JSON.parse(readFileSync(join(root, code, file), "utf8")) as Record<string, string>);
    const jargon = readdirSync(root).flatMap((code) => readdirSync(join(root, code))
      .filter((file) => file !== "admin.json")
      .flatMap((file) => strings(code, file).filter(([, text]) => /semantic|sémantique|keyword|mot-clé/i.test(text))
        .map(([key]) => `${code}/${file}: ${key}`)));
    expect(jargon).toEqual([]);
  });

  it("finds none in app/src: no markup tell outside the token file, no pictograph in a component's strings, one "
    + "frosted element", () => {
    const sources = filesUnder(["src", "studio", join("scripts", "prerender")], /\.(ts|tsx|css)$/)
      .filter((path) => path !== TOKENS && !basename(path).startsWith("generated-"));
    expect(findings(sources, (_path, source) => markupFindings(source))).toEqual([]);
    expect(findings(sources.filter((path) => /\.tsx?$/.test(path)),
      (path, source) => lines(path, source, (node) => PICTOGRAPH.test(shown(node))))).toEqual([]);
    expect(sources.reduce((n, path) => n + frosted(readFileSync(join(APP, path), "utf8")), 0)).toBeLessThanOrEqual(1);
  });

  it("finds none in the pages the prerender writes", () => {
    const out = mkdtempSync(join(tmpdir(), "mvr-slop-"));
    writeFileSync(join(out, "index.html"),
      '<!doctype html><html><head><title>t</title></head><body><div id="root"></div></body></html>');
    execFileSync("node", ["--experimental-strip-types", "scripts/prerender/main.ts"], {
      cwd: APP, stdio: "pipe",
      env: { ...process.env, MVR_SITE_URL: "https://example.com", MVR_PRERENDER_OUT: out,
        MVR_READ_MODEL_DIR: join(process.env.MVR_E2E_FIXTURE ?? "", "dist", "public") },
    });
    const pages = readdirSync(out, { recursive: true, encoding: "utf8" }).filter((f) => f.endsWith(".html"));
    expect(pages.flatMap((path) => pageFindings(readFileSync(join(out, path), "utf8")).map((f) => `${path}: ${f}`)))
      .toEqual([]);
  }, 60_000);
});
