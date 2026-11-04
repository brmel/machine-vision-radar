import { readdirSync, readFileSync } from "node:fs";
import type { MessageKey, Messages } from "../../src/shell/i18n/messages.ts";
import { DEFAULT_LANGUAGE, LANGUAGES } from "../../src/domain/languages.ts";

export const EN = DEFAULT_LANGUAGE.code;

export const MESSAGES: Readonly<Record<string, Messages>> = Object.fromEntries(LANGUAGES.map((l) => {
  const folder = new URL(`../../src/shell/i18n/messages/${l.code}/`, import.meta.url);
  // Justification (typed boundary): a language's files hold every key of the default language's between them (i18n-keys
  return [l.code, Object.assign({},
    ...readdirSync(folder).map((file) => JSON.parse(readFileSync(new URL(file, folder), "utf8")))) as Messages];
}));

export const inEveryLanguage = (key: MessageKey): string =>
  [...new Set(Object.values(MESSAGES).map((m) => m[key]))].join(" · ");
