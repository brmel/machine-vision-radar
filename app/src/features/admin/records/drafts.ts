import { RefusedChange, type ChangeDraft, type Json, type JsonRecord } from "../../../domain/ports/review/Review.ts";
import type { EditedRecord } from "../../../domain/ports/review/CatalogEditor.ts";
import type { AdminModel, EntityShape, PartialDate } from "../../../domain/views.ts";
import { ENTITY_KINDS } from "../../../domain/views.ts";
import { entity, isKind } from "../model.ts";

const CROCKFORD = "0123456789abcdefghjkmnpqrstvwxyz";

export const isRecord = (value: Json | null | undefined): value is JsonRecord => value !== null
  && typeof value === "object" && !Array.isArray(value);

function newId(prefix: string): string {
  return `${prefix}_${Array.from(crypto.getRandomValues(new Uint8Array(10)), (b) => CROCKFORD[b % 32]).join("")}`;
}

export const instant = (): string => new Date().toISOString().replace(/\.\d+Z$/, "Z");

export const FILLED: readonly string[] = ["id", "version", "mime", "bytes", "sha256", "fetched_at"];

export function newRecord(shape: EntityShape, given: URLSearchParams): JsonRecord {
  const start = shape.fields.flatMap((f): [string, Json][] => {
    const value = given.get(f.name);
    if (value !== null) return [[f.name, f.type === "array" ? [value] : value]];
    if (f.type === "Instant") return [[f.name, instant()]];
    return f.type === "boolean" ? [[f.name, false]] : [];
  });
  return { id: newId(shape.prefix), ...Object.fromEntries(start) };
}

const PRECISIONS: readonly [RegExp, PartialDate["precision"]][] = [[/^\d{4}$/, "year"], [/^\d{4}-H[12]$/, "half"],
  [/^\d{4}-Q[1-4]$/, "quarter"], [/^\d{4}-\d{2}$/, "month"], [/^\d{4}-\d{2}-\d{2}$/, "day"]];

export function partialDate(text: string): Pick<PartialDate, "value" | "precision"> | null {
  const precision = PRECISIONS.find(([pattern]) => pattern.test(text.trim()))?.[1];
  return precision ? { value: text.trim(), precision } : null;
}

export type SourceChoice = { readonly existing: string }
  | { readonly type: string; readonly url: string; readonly title: string };

export interface NewProduct {
  readonly name: string;
  readonly org: string;
  readonly role: string;
}

interface RecordDraft {
  readonly record: JsonRecord;
  readonly product: NewProduct | null;
  readonly specs: Readonly<Record<string, Json | null>>;
  readonly method: string;
  readonly source: SourceChoice | null;
  readonly reason: string;
}

const same = (a: Json | undefined, b: Json | undefined): boolean => JSON.stringify(a) === JSON.stringify(b);

export function claimsOf(related: readonly JsonRecord[], id: string): Readonly<Record<string, JsonRecord>> {
  const ranked = related.filter((r) => isKind("Claim")(r) && r.subject === id)
    .sort((a, b) => Number(a.rank) - Number(b.rank));
  return Object.fromEntries(ranked.filter((c, i) => ranked.findIndex((o) => o.spec_key === c.spec_key) === i)
    .map((c) => [String(c.spec_key), c]));
}

const claimPut = (held: JsonRecord | undefined, subject: string, key: string, value: Json, method: string,
  refs: string[]): JsonRecord =>
  ({ ...(held ?? { id: newId(ENTITY_KINDS.Claim.prefix), subject, spec_key: key, rank: 1 }), value, method,
    recorded_at: instant(), source_refs: refs });

const changesFor = (puts: readonly JsonRecord[], cleared: readonly string[], reason: string,
  refs: string[]): ChangeDraft[] => [
  ...puts.map((put): ChangeDraft => ({ op: "put", entity: put, reason, source_refs: refs })),
  ...cleared.map((claim): ChangeDraft => ({ op: "retract", id: claim, reason, source_refs: refs })),
];

function around(draft: RecordDraft, existing: EditedRecord | null, id: string, source: string): JsonRecord[] {
  const name = draft.product?.name.trim()
    ? [{ id: newId(ENTITY_KINDS.Name.prefix), subject: id, is_primary: true, value: draft.product.name.trim() }] : [];
  const maker = draft.product ? [{ id: newId(ENTITY_KINDS.ProductOrgRole.prefix), product: id, org: draft.product.org,
    role: draft.product.role, source_refs: [source] }] : [];
  const held = claimsOf(existing?.related ?? [], id);
  const claims = Object.entries(draft.specs).flatMap(([key, value]) => (value === null || same(held[key]?.value, value)
    ? [] : [claimPut(held[key], id, key, value, draft.method, [source])]));
  return [...name, ...maker, ...claims];
}

const citedBy = (record: JsonRecord): string[] =>
  (Array.isArray(record.source_refs) ? record.source_refs.map(String) : []);

export function chosenSource(picked: SourceChoice | null, record: JsonRecord): SourceChoice {
  const [own] = citedBy(record);
  return picked ?? (own ? { existing: own } : { type: "", url: "", title: "" });
}

export const namesSource = (source: SourceChoice): boolean => "existing" in source || Boolean(source.type);

function cited(choice: SourceChoice | null): { readonly id: string; readonly added: JsonRecord[] } {
  if (!choice) return { id: "", added: [] };
  if ("existing" in choice) return { id: choice.existing, added: [] };
  const added = { id: newId(ENTITY_KINDS.Source.prefix), type: choice.type, retrieved_at: instant(),
    ...(choice.url.trim() ? { url: choice.url.trim() } : {}),
    ...(choice.title.trim() ? { title: choice.title.trim() } : {}) };
  return { id: added.id, added: [added] };
}

export function changesOf(model: AdminModel, kind: string, draft: RecordDraft,
    existing: EditedRecord | null): ChangeDraft[] {
  const id = String(draft.record.id);
  const source = cited(draft.source);
  const refs = source.id ? [source.id] : [];
  const sourced = entity(model, kind).fields.some((f) => f.name === "source_refs");
  const record = sourced ? { ...draft.record, source_refs: [...new Set([...citedBy(draft.record), ...refs])] }
    : draft.record;
  const main = !existing || !same(existing.record, record) ? [record] : [];
  const cleared = Object.entries(draft.specs).filter(([, v]) => v === null).flatMap(([key]) =>
    (existing?.related ?? []).filter((r) => isKind("Claim")(r) && r.subject === id && r.spec_key === key)
      .map((r) => String(r.id)));
  const puts = [...source.added, ...main, ...around(draft, existing, id, source.id)];
  return changesFor(puts, cleared, draft.reason, refs);
}

export function gridChanges(key: string, held: Readonly<Record<string, JsonRecord | undefined>>,
    set: Readonly<Record<string, Json | null>>, method: string, choice: SourceChoice, reason: string): ChangeDraft[] {
  const source = cited(choice);
  const refs = source.id ? [source.id] : [];
  const puts = Object.entries(set).flatMap(([product, value]) => (value === null || same(held[product]?.value, value)
    ? [] : [claimPut(held[product], product, key, value, method, refs)]));
  const cleared = Object.entries(set)
    .flatMap(([product, value]) => (value === null && held[product] ? [String(held[product]?.id)] : []));
  return changesFor([...source.added, ...puts], cleared, reason, refs);
}

function textsIn(value: Json | undefined): readonly string[] | null {
  if (value === undefined) return [];
  const texts = Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
  return Array.isArray(value) && texts.length === value.length ? texts : null;
}

function changeDraft(change: Json, n: number): ChangeDraft {
  const [reason, refs] = isRecord(change) ? [change.reason, textsIn(change.source_refs)] : [null, null];
  if (isRecord(change) && typeof reason === "string" && refs) {
    if (change.op === "put" && isRecord(change.entity))
      return { op: "put", entity: change.entity, reason, source_refs: refs };
    if (change.op === "retract" && typeof change.id === "string")
      return { op: "retract", id: change.id, reason, source_refs: refs };
  }
  throw new RefusedChange(`changes[${n}] puts an entity or retracts an id, with its reason and source_refs`, []);
}

export function changeDrafts(text: string): readonly ChangeDraft[] {
  let raw: Json;
  try {
    raw = JSON.parse(text);
  } catch (err) {
    throw new RefusedChange("the changeset is not JSON", [String(err)]);
  }
  if (!isRecord(raw) || !Array.isArray(raw.changes) || raw.changes.length === 0)
    throw new RefusedChange('a changeset is {"changes": [...]} with at least one change', []);
  return raw.changes.map(changeDraft);
}
