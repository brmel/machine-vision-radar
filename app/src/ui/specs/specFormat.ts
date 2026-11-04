import { DEFAULT_LANGUAGE, intlLocale } from "../../domain/languages.ts";
import type { CategoryEntry, FacetView, LocalizedText, PartialDate, SourceView, SpecLabel, TermEntry,
  ViewValue } from "../../domain/views.ts";

export type SpecDefinitions = Readonly<Record<string, SpecLabel>>;

export interface SpecValueLabels {
  unknown: string;
  yes: string;
  no: string;
  locale: string;
}

function translation(text: LocalizedText, locale: string): string | undefined {
  const texts: readonly (readonly [string, string | undefined])[] = Object.entries(text);
  return texts.find(([code]) => code === locale)?.[1];
}

export function localized(text: LocalizedText, locale: string): string {
  return translation(text, locale) ?? text.en;
}

export function localizedLang(text: LocalizedText, locale: string): string {
  return translation(text, locale) === undefined ? DEFAULT_LANGUAGE.code : locale;
}

export function termLabel(terms: readonly (CategoryEntry | TermEntry)[], termId: string, locale: string): string {
  const term = terms.find((t) => t.id === termId);
  if (!term) throw new Error(`termLabel: unknown term ${termId}`);
  return localized(term.label, locale);
}

export function formatNumber(value: number, locale: string): string {
  return new Intl.NumberFormat(intlLocale(locale), { maximumFractionDigits: 6 }).format(value);
}

export function formatDate(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) throw new Error(`formatDate: not an ISO date: ${iso}`);
  return new Intl.DateTimeFormat(intlLocale(locale),
    { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(date);
}

export function formatInstant(iso: string, locale: string): string {
  return new Intl.DateTimeFormat(intlLocale(locale), { dateStyle: "medium", timeStyle: "medium" })
    .format(new Date(iso));
}

export function formatPartialDate(date: PartialDate, locale: string): string {
  const [year, month, day] = date.value.split("-").map(Number);
  if (date.precision === "day") return formatDate(`${date.value}T00:00:00Z`, locale);
  if (date.precision === "month") {
    return new Intl.DateTimeFormat(intlLocale(locale), { month: "long", year: "numeric", timeZone: "UTC" })
      .format(new Date(Date.UTC(year, month - 1, day || 1)));
  }
  return date.value;
}

function withUnit(text: string, unit: string | undefined, place: "value" | "label"): string {
  return place === "value" && unit ? `${text}\u00A0${unit}` : text;
}

export function formatSpecValueText(val: ViewValue | undefined, labels: SpecValueLabels,
    unit: "value" | "label" = "value"): string {
  if (val === undefined) return labels.unknown;
  if ("boolean" in val) return val.boolean ? labels.yes : labels.no;
  if ("string" in val) return val.string;
  if ("terms" in val) return val.terms.map((t) => localized(t.label, labels.locale)).join(", ");
  if ("term" in val) return localized(val.term.label, labels.locale);
  if ("none" in val) return localized(val.none.label, labels.locale);
  if ("range" in val) return withUnit(`${formatNumber(val.range.min, labels.locale)}–${formatNumber(val.range.max,
    labels.locale)}`, val.range.unit, unit);
  return withUnit(formatNumber(val.quantity.value, labels.locale), val.quantity.unit, unit);
}

export function specValueLang(val: ViewValue | undefined, locale: string): string | undefined {
  if (locale === DEFAULT_LANGUAGE.code || val === undefined) return undefined;
  if ("string" in val) return DEFAULT_LANGUAGE.code;
  const terms = "terms" in val ? val.terms : "term" in val ? [val.term] : [];
  return terms.some((t) => translation(t.label, locale) === undefined) ? DEFAULT_LANGUAGE.code : undefined;
}

export function facetLabel(facet: FacetView, locale: string): string {
  const label = localized(facet.label, locale);
  return facet.unit ? `${label} (${facet.unit})` : label;
}

export function formatSpecLabel(specKey: string, specDefs: SpecDefinitions, locale: string): string {
  const def = specDefs[specKey];
  if (!def) throw new Error(`formatSpecLabel: no spec definition for '${specKey}'`);
  return localized(def.label, locale);
}

export function specRowLabel(specKey: string, specDefs: SpecDefinitions, locale: string): string {
  const label = formatSpecLabel(specKey, specDefs, locale);
  const unit = specDefs[specKey].unit;
  return unit ? `${label} (${unit})` : label;
}

export function formatCountry(code: string, locale: string): string {
  const name = new Intl.DisplayNames([intlLocale(locale)], { type: "region" }).of(code);
  if (!name) throw new Error(`formatCountry: unknown region code ${code}`);
  return name;
}

interface KeySpecRow {
  readonly key: string;
  readonly label: string;
  readonly value: string;
  readonly lang: string | undefined;
}

export function keySpecRows(specs: Readonly<Record<string, ViewValue>>, keys: readonly string[],
    specDefs: SpecDefinitions, labels: SpecValueLabels): KeySpecRow[] {
  return keys
    .filter((key) => key in specs && key in specDefs)
    .slice(0, 3)
    .map((key) => ({
      key,
      label: formatSpecLabel(key, specDefs, labels.locale),
      value: formatSpecValueText(specs[key], labels),
      lang: specValueLang(specs[key], labels.locale),
    }));
}

export function sourceLinkText(source: SourceView): string {
  if (source.title) return source.title;
  if (!source.url) throw new Error(`sourceLinkText: source ${source.id} has neither title nor URL`);
  return new URL(source.url).hostname.replace(/^www\./, "");
}
