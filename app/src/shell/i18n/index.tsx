import { createContext, useContext, useState, useEffect, useCallback, type FC, type ReactNode } from "react";
import { defaultLanguage, LANGUAGES, type Language } from "../../domain/languages.ts";
import { fill, plural, type MessageKey, type Messages } from "./messages.ts";
import { save } from "../root/preferences.ts";

const FILES =
  import.meta.glob<Readonly<Record<string, string>>>("./messages/*/*.json", { eager: true, import: "default" });

export const MESSAGES: Readonly<Record<string, Messages>> = Object.entries(FILES)
  .reduce<Record<string, Messages>>((out, [path, strings]) => {
  const code = path.split("/")[2];
  // Justification (typed boundary): each language's files hold every key between them (the i18n-keys guard).
  return { ...out, [code]: { ...out[code], ...strings } as Messages };
}, {});

export const LOCALE_KEY = "machineVisionRadar.locale";

interface I18nContextValue {
  locale: string;
  setLocale: (locale: string) => void;
  t: (key: MessageKey, params?: Record<string, string | number>) => string;
  plural: (one: MessageKey, other: MessageKey, count: number) => string;
  locales: readonly Language[];
}

const I18nContext = createContext<I18nContextValue | null>(null);

export const I18nProvider: FC<{ children: ReactNode; preferred?: readonly string[]; languages?: readonly Language[];
  messages?: Readonly<Record<string, Messages>> }> = ({
  children,
  preferred = [],
  languages = LANGUAGES,
  messages = MESSAGES,
}) => {
  const [locale, setLocaleState] =
    useState(() => preferred.find((code) => languages.some((l) => l.code === code)) ?? defaultLanguage(languages).code);
  const meta = languages.find((l) => l.code === locale) ?? defaultLanguage(languages);

  const setLocale = (next: string) => {
    setLocaleState(next);
    save(LOCALE_KEY, next, "locale preference not saved");
  };

  useEffect(() => {
    document.documentElement.lang = meta.code;
    document.documentElement.dir = meta.dir;
  }, [meta]);

  const t = useCallback((key: MessageKey, params?: Record<string, string | number>): string =>
    fill(messages[meta.code][key], params), [messages, meta]);

  const pluralOf = useCallback((one: MessageKey, other: MessageKey, count: number): string =>
    plural(messages[meta.code], meta.intl, one, other, count), [messages, meta]);

  return (
    <I18nContext.Provider value={{ locale: meta.code, setLocale, t, plural: pluralOf,
      locales: languages }}>{children}</I18nContext.Provider>
  );
};

export const useI18n = (): I18nContextValue => {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within an I18nProvider");
  return ctx;
};
