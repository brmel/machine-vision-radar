import { useState, type ChangeEvent, type FC } from "react";
import type { CatalogEditor, EditedRecord } from "../../../../domain/ports/review/CatalogEditor.ts";
import type { Json } from "../../../../domain/ports/review/Review.ts";
import { CONTROL, Field, PageHeader, RowList, StatePanel, localized, useRead } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { logger } from "../../../../shell/logger.ts";
import { isKind, terms, useAdmin } from "../../model.ts";
import { usePaged } from "../../useLoad.tsx";
import { claimsOf, gridChanges, namesSource, type SourceChoice } from "../drafts.ts";
import { SpecInput } from "../fields/spec/SpecInput.tsx";
import { TermSelect } from "../fields/TermSelect.tsx";
import { Filing } from "./Filing.tsx";

const useRecords = (editor: CatalogEditor, page: string): Readonly<Record<string, EditedRecord>> =>
  useRead(() => Promise.all(page.split(",").filter(Boolean).map((id) => editor.record(id)))
    .then((found) => Object.fromEntries(found.map((r) => [String(r.record.id), r]))), `grid#${page}`,
  (err) => logger.warn("admin: the grid's records did not load", { page: "admin" }, err)).value ?? {};

function chosen(search: string, profiles: Readonly<Record<string,
    { readonly core: readonly string[]; readonly detail: readonly string[] }>>) {
  const params = new URLSearchParams(search);
  const category = params.get("category") ?? Object.keys(profiles)[0] ?? "";
  const keys = [...(profiles[category]?.core ?? []), ...(profiles[category]?.detail ?? [])];
  const asked = params.get("spec") ?? "";
  return { category, keys, key: keys.includes(asked) ? asked : keys[0] ?? "" };
}

export const GridView: FC<{ search: string }> = ({ search }) => {
  const { model, editor, review, onNavigate } = useAdmin();
  const { t, locale } = useI18n();
  const { category, keys, key } = chosen(search, model.profiles);
  const list =
    usePaged((cursor) => editor.records("Product", "", cursor, category), `grid-${category}`, "/grid", search, 4);
  const shown = list.value?.records ?? [];
  const records = useRecords(editor, shown.map((r) => r.id).join(","));
  const [set, setSet] = useState<Readonly<Record<string, Json | null>>>({});
  const held = Object.fromEntries(shown.map((r) => [r.id, claimsOf(records[r.id]?.related ?? [], r.id)[key]]));
  const sources = Object.values(records).flatMap((r) => r.related.filter(isKind("Source")));
  const go = (next: { category?: string; spec?: string }) => {
    setSet({});
    onNavigate(`/grid?${new URLSearchParams({ category: next.category ?? category,
      ...(next.spec ? { spec: next.spec } : {}) })}`);
  };
  const onFile = async (method: string, source: SourceChoice, reason: string): Promise<readonly string[]> => {
    const changed = Object.keys(set);
    if (!reason || !namesSource(source) || changed.length === 0) return [t("adminNeedReasonSource")];
    onNavigate(`/queue/${(await review.submit({ filesOn: "update", reason, subject: changed[0],
      changes: gridChanges(key, held, set, method, source, reason) })).id}`);
    return [];
  };

  return (
    <section className="space-y-5">
      <PageHeader title={t("adminGridTitle")} />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <TermSelect label={t("adminGridCategory")} terms={terms(model, "categories")} value={category}
          onChange={(c) => go({ category: c })} empty={false} />
        <Field label={t("adminGridSpec")}>
          <select className={CONTROL} value={key}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => go({ spec: e.target.value })}>
            {keys.map((k) => <option key={k} value={k}>{localized(model.specs[k]?.label ?? {}, locale)}</option>)}
          </select>
        </Field>
      </div>
      {list.count}
      {!list.value ? list.pending : shown.length === 0 ? <StatePanel tone="empty" title={t("adminNoRecords")} /> : (
        <RowList>
          {shown.map((r) => (
            <li key={r.id} className="px-3 py-2">
              <SpecInput specKey={key} label={r.label} value={r.id in set ? set[r.id] : held[r.id]?.value}
                onChange={(v) => setSet((s) => ({ ...s, [r.id]: v }))} />
            </li>
          ))}
        </RowList>
      )}
      {list.pager}
      {shown.length > 0 && <Filing sources={sources} onFile={onFile} />}
    </section>
  );
};
