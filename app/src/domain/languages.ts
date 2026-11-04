import config from "../../../contracts/languages.json" with { type: "json" };

export interface Language {
  readonly code: string;
  readonly label: string;
  readonly name: string;
  readonly dir: "ltr" | "rtl";
  readonly intl: string;
  readonly default: boolean;
}

type LanguageEntry = Omit<Language, "dir"> & { readonly dir: string };

const isDirection = (dir: string): dir is Language["dir"] => dir === "ltr" || dir === "rtl";

export function parseLanguages(entries: readonly LanguageEntry[]): readonly Language[] {
  const languages = entries.map(({ dir, ...entry }): Language => {
    if (!isDirection(dir)) throw new Error(`languages.json: ${entry.code} has direction ${dir}`);
    return { ...entry, dir };
  });
  if (languages.filter((l) => l.default).length !== 1)
    throw new Error("languages.json: exactly one language is the default");
  return languages;
}

export const LANGUAGES = parseLanguages(config);

export const defaultLanguage = (languages: readonly Language[]): Language => languages.find((l) => l.default)
  ?? languages[0];

export const DEFAULT_LANGUAGE = defaultLanguage(LANGUAGES);

export const intlLocale = (code: string): string => (LANGUAGES.find((l) => l.code === code) ?? DEFAULT_LANGUAGE).intl;
