import admin from "./messages/en/admin.json" with { type: "json" };
import agents from "./messages/en/agents.json" with { type: "json" };
import legal from "./messages/en/legal.json" with { type: "json" };
import site from "./messages/en/site.json" with { type: "json" };
import { DEFAULT_LANGUAGE } from "../../domain/languages.ts";
import type { SpecValueLabels } from "../../ui/specs/specFormat.ts";

const defaults = { ...site, ...legal, ...admin, ...agents };

export type MessageKey = keyof typeof defaults;
export type Messages = Readonly<Record<MessageKey, string>>;

export const DEFAULT_MESSAGES: Messages = defaults;

export const DEFAULT_VALUE_LABELS: SpecValueLabels = { unknown: defaults.unknownValue, yes: defaults.yesValue,
  no: defaults.noValue, locale: DEFAULT_LANGUAGE.code };

export const fill = (text: string, params: Readonly<Record<string, string | number>> = {}): string =>
  Object.entries(params).reduce((filled, [name, value]) => filled.replaceAll(`{${name}}`, String(value)), text);

export const plural = (messages: Messages, intl: string, one: MessageKey, other: MessageKey, count: number): string =>
  fill(messages[new Intl.PluralRules(intl).select(count) === "one" ? one : other],
    { count: new Intl.NumberFormat(intl).format(count) });
