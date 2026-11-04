import filler from "../../../data/no_filler.json" with { type: "json" };
import { DEFAULT_LANGUAGE } from "../../src/domain/languages.ts";

export const FPS = 30;
export const HOOK_SECONDS = 2;
export const END_SECONDS = 2.5;
const MOST_SECONDS = 30;

const SHOWS = ["footage", "card"] as const;
type Segment = { shows: (typeof SHOWS)[number]; caption: string; seconds: number };
export type ClipScript = { hook: string; segments: Segment[]; about: string[] };

const PHRASES =
  [...filler.anywhere, ...filler.copy].map((b) => ({ re: new RegExp(b.pattern, "iu"), reason: b.reason }));
const CLAIMS = filler.claims.map((b) => ({ re: new RegExp(b.pattern, "u"), reason: b.reason, language: b.language }));

const found = (text: string, banned: readonly { re: RegExp; reason: string }[]): string[] =>
  banned.flatMap((b) => text.match(b.re)?.slice(0, 1).map((m) => `"${m}": ${b.reason}`) ?? []);

export const bannedPhrases = (text: string): string[] => found(text, PHRASES);

export const bannedClaims = (text: string, language: string): string[] =>
  found(text, CLAIMS.filter((b) => b.language === language));

export const bannedIn = (text: string): string[] =>
  [...bannedPhrases(text), ...bannedClaims(text, DEFAULT_LANGUAGE.code)];

const FIGURE = /\d+(?:,\d{3})*(?:\.\d+)?/g;
const figures = (text: string): string[] => (text.match(FIGURE) ?? []).map((f) => f.replaceAll(",", ""));

export function unheld(text: string, facts: string): string[] {
  const held = new Set(figures(facts));
  return [...new Set(figures(text))].filter((figure) => !held.has(figure));
}

const fieldsOf = (raw: unknown): ReadonlyMap<string, unknown> =>
  new Map(typeof raw === "object" && raw !== null ? Object.entries(raw) : []);

const text = (value: unknown, where: string): string => {
  if (typeof value !== "string" || !value.trim()) throw new Error(`clip script: ${where} is a non-empty text`);
  const [found] = bannedIn(value);
  if (found) throw new Error(`clip script: ${where} says ${found}`);
  return value.trim();
};

function segment(raw: unknown, i: number): Segment {
  const fields = fieldsOf(raw);
  const seconds = fields.get("seconds");
  if (typeof seconds !== "number" || seconds < 1)
    throw new Error(`clip script: segment ${i + 1} lasts at least 1 second`);
  const shows = SHOWS.find((f) => f === fields.get("shows"));
  if (!shows) throw new Error(`clip script: segment ${i + 1} shows ${SHOWS.join(" or ")}`);
  return { shows, caption: text(fields.get("caption"), `segment ${i + 1}'s caption`), seconds };
}

export function parseScript(raw: unknown): ClipScript {
  const fields = fieldsOf(raw);
  const listed = fields.get("segments");
  const segments = Array.isArray(listed) ? listed.map(segment) : [];
  if (segments.length === 0 || new Set(segments.map((s) => s.shows)).size < segments.length)
    throw new Error("clip script: its footage, its card, or both, each once");
  const about = fields.get("about");
  const script = { hook: text(fields.get("hook"), "the hook"), segments,
    about: Array.isArray(about) ? about.map((a, i) => text(a, `about ${i + 1}`)) : [] };
  if (seconds(script) > MOST_SECONDS)
    throw new Error(`clip script: ${seconds(script)} s; a clip lasts at most ${MOST_SECONDS} s`);
  return script;
}

export const shown = (script: ClipScript): string => [script.hook, ...script.segments.map((s) => s.caption)].join("\n");

export const seconds = (script: ClipScript): number =>
  HOOK_SECONDS + script.segments.reduce((n, s) => n + s.seconds, 0) + END_SECONDS;

const stamp = (at: number): string => {
  const ms = Math.round(at * 1000);
  const pad = (n: number, w = 2) => String(n).padStart(w, "0");
  const [h, m, s] = [ms / 3_600_000, (ms / 60_000) % 60, (ms / 1000) % 60].map((n) => pad(Math.floor(n)));
  return `${h}:${m}:${s},${pad(ms % 1000, 3)}`;
};

export function srt(script: ClipScript): string {
  const cues = [{ text: script.hook, from: 0, to: HOOK_SECONDS }];
  for (const s of script.segments)
    cues.push({ text: s.caption, from: cues[cues.length - 1].to, to: cues[cues.length - 1].to + s.seconds });
  return cues.map((c, i) => `${i + 1}\n${stamp(c.from)} --> ${stamp(c.to)}\n${c.text}\n`).join("\n");
}
