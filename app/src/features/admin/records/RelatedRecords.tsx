import { useState, type FC } from "react";
import type { JsonRecord } from "../../../domain/ports/review/Review.ts";
import type { EntityShape } from "../../../domain/views.ts";
import { RowList, Section, localized } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useAdmin } from "../model.ts";
import { AdminLink, Pager, pageRows } from "../useLoad.tsx";

type Listed = Pick<EntityShape, "id" | "label" | "prefix"> & { readonly screen?: string };

export const RelatedRecords: FC<{ id: string; kind: string; related: readonly JsonRecord[];
  onUseThumbnail?: (docId: string) => void }> = ({ id, kind, related, onUseThumbnail }) => {
  const { model } = useAdmin();
  const { t, locale } = useI18n();
  const [pages, setPages] = useState<Readonly<Record<string, number>>>({});
  const turn = (kind: string) => (page: number) => setPages((p) => ({ ...p, [kind]: page }));
  const kinds: readonly Listed[] = [...model.entities, ...model.owned];
  const groups = kinds.map((k) => ({ k, rows: related.filter((r) => String(r.id).startsWith(`${k.prefix}_`)) }))
    .filter((g) => g.rows.length > 0);
  const adds = model.entities.flatMap((e) => e.fields.filter((f) => f.refs.includes(kind) && f.name !== "source_refs")
    .map((f) => ({
    path: `/records/new/${e.id}?${new URLSearchParams({ [f.name]: id })}`,
    label: t("adminAdd", { kind: localized(e.label, locale), field: localized(f.label, locale) }),
  })));
  if (groups.length === 0 && adds.length === 0) return null;
  return (
    <Section title={t("adminRelated")}>
      {groups.map(({ k, rows }) => (
        <div key={k.id} className="space-y-1">
          <h3 className="text-body font-heading">{localized(k.label, locale)}</h3>
          <RowList>
            {pageRows(rows, pages[k.id] ?? 1).map((r) => (
              <li key={String(r.id)} className="p-3">
                <div className="flex items-center justify-between gap-2">
                  <AdminLink to={k.screen ?? `/records/${r.id}`}
                    className="font-mono underline break-all">{String(r.id)}</AdminLink>
                  {kind === "Product" && k.id === "Document" && onUseThumbnail
                    && String(r.mime).startsWith("image/") && (
                      <button type="button" onClick={() => onUseThumbnail(String(r.id))}
                        className="text-caption font-medium text-focus hover:underline">
                        {t("adminUseAsThumbnail")}
                      </button>
                    )}
                </div>
                <p className="text-caption text-muted break-words">
                  {Object.entries(r)
                    .flatMap(([key, v]) => (key !== "id" && typeof v === "string" && v !== id ? [v] : [])).join(" · ")}
                </p>
              </li>
            ))}
          </RowList>
          <Pager page={pages[k.id] ?? 1} total={rows.length} onPage={turn(k.id)} />
        </div>
      ))}
      <ul className="flex flex-wrap gap-2">
        {adds.map((a) => (
          <li key={a.path}><AdminLink to={a.path} className="text-caption underline">{a.label}</AdminLink></li>
        ))}
      </ul>
    </Section>
  );
};
