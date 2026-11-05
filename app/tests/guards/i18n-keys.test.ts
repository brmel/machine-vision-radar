import { readdirSync, readFileSync } from "node:fs";
import { basename, join } from "node:path";
import { describe, expect, it } from "vitest";
import { DEFAULT_LANGUAGE, LANGUAGES } from "../../src/domain/languages.ts";
import { MESSAGES } from "../../src/shell/i18n/index.tsx";
import { DEFAULT_MESSAGES } from "../../src/shell/i18n/messages.ts";
import { APP, filesUnder, findings } from "./source.ts";

const MESSAGES_PATH = join("src", "shell", "i18n", "messages");
const MESSAGE_DIR = join(APP, MESSAGES_PATH);
const CONFIG = join("..", "contracts", "languages.json");

function sourceFiles(...dirs: string[]): string[] {
  return filesUnder(dirs, /\.(tsx?|json)$/)
    .filter((path) => path !== CONFIG && !path.startsWith(MESSAGES_PATH) && !basename(path).startsWith("generated-"));
}

function languageLiterals(source: string, codes: readonly string[]): number[] {
  const literal = new RegExp(`["'\`](?:${codes.join("|")})["'\`]`);
  return source.split("\n").flatMap((line, i) => (literal.test(line) ? [i + 1] : []));
}

describe("languages and their strings", () => {
  const codes = LANGUAGES.map((l) => l.code);

  it("has one messages folder per language of the config, none else, each with the same files", () => {
    expect(readdirSync(MESSAGE_DIR).sort()).toEqual([...codes].sort());
    for (const code of codes) expect(readdirSync(join(MESSAGE_DIR, code)).sort(), code)
      .toEqual(readdirSync(join(MESSAGE_DIR, DEFAULT_LANGUAGE.code)).sort());
  });

  it("keeps French punctuation on its word's line", () => {
    expect(Object.entries(MESSAGES.fr).filter(([, text]) => /[ \t][;:?!»]|«[ \t]/.test(text)).map(([key]) => key))
      .toEqual([]);
  });

  it("gives every language every key of the default language, each declared once and non-empty", () => {
    const keys = Object.keys(DEFAULT_MESSAGES).sort();
    for (const code of codes) {
      const declared = readdirSync(join(MESSAGE_DIR, code)).flatMap((file) =>
        [...readFileSync(join(MESSAGE_DIR, code, file), "utf8").matchAll(/^ {2}"(\w+)": /gm)].map((m) => m[1]));
      expect(declared.filter((key, i) => declared.indexOf(key) !== i), code).toEqual([]);
      expect(Object.keys(MESSAGES[code]).sort(), code).toEqual(keys);
      expect(Object.entries(MESSAGES[code]).filter(([, text]) => !text.trim()).map(([key]) => key), code).toEqual([]);
    }
  });

  it("names each admin section once in every language", () => {
    for (const code of codes) {
      const nav = Object.entries(MESSAGES[code]).filter(([key]) => key.startsWith("adminNav")).map(([, text]) => text);
      expect(nav.filter((text, i) => nav.indexOf(text) !== i), code).toEqual([]);
    }
  });

  it("translates every string, except names and words French writes the same way", () => {
    const sameInBoth =
      new Set(["adminSearchNavIndex", "adminSearchNavConsole", "adminConsoleQuestion", "footerVersion", "tabSources",
        "navAdmin", "versionField_label", "adminActorAgent", "adminActorImport", "mediaSource", "adminNavAgents",
        "agentsClientClaudeCode", "agentsClientCursor", "productDescription"]);
    const untranslated = Object.entries(MESSAGES.fr).filter(([key, text]) =>
      text === MESSAGES.en[key as keyof typeof DEFAULT_MESSAGES] && !sameInBoth.has(key)).map(([key]) => key);
    expect(untranslated).toEqual([]);
  });

  it("declares no key that the app never uses", () => {
    const code = sourceFiles("src", "studio", join("scripts", "prerender"))
      .map((path) => readFileSync(join(APP, path), "utf8")).join("\n");
    const unused = Object.keys(DEFAULT_MESSAGES).filter((k) => !new RegExp(`\\b${k}\\b`).test(code));
    expect(unused).toEqual([]);
  });

  it("finds a language code typed in code, on a fixture", () => {
    const fixture =
      'const a = locale === "fr" ? 1 : 2;\nconst b = `en`;\nconst c = text.en ?? DEFAULT_LANGUAGE.code; // en, fr\n';
    expect(languageLiterals(fixture, codes)).toEqual([1, 2]);
  });

  it("names no language in app/src outside languages.json and the messages files", () => {
    expect(findings(sourceFiles("src", "studio"), (_path, source) => languageLiterals(source, codes))).toEqual([]);
  });
});
