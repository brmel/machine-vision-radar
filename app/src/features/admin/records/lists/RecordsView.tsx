import type { FC, FocusEvent } from "react";
import { Button, CONTROL, Field, PageHeader, RowList, Segmented, StatePanel } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { AdminLink, usePaged } from "../../useLoad.tsx";
import { SECTIONS, useAdmin } from "../../model.ts";

interface Props {
  section: string;
  search: string;
}

export const RecordsView: FC<Props> = ({ section, search }) => {
  const { editor, onNavigate } = useAdmin();
  const { t } = useI18n();
  const { kind, label } = SECTIONS[section];
  const query = new URLSearchParams(search).get("q") ?? "";
  const list = usePaged((cursor) => editor.records(kind, query, cursor), kind, `/${section}`, search, 4);
  const onSearch = (event: FocusEvent<HTMLInputElement>) =>
    onNavigate(event.target.value ? `/${section}?q=${encodeURIComponent(event.target.value)}` : `/${section}`);
  return (
    <section className="space-y-4">
      <PageHeader title={t(label)} actions={<Button variant="primary"
        onClick={() => onNavigate(`/records/new/${kind}`)}>{t("adminNew")}</Button>} />
      <Segmented look="tab" label={t("adminNavCatalog")} value={section} onChange={(key) => onNavigate(`/${key}`)}
        options={Object.entries(SECTIONS).map(([key, tab]) => ({ id: key, label: t(tab.label) }))} />
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Field label={t("adminSearch")} className="w-full max-w-md">
          <input type="search" className={CONTROL} defaultValue={query} onBlur={onSearch}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()} />
        </Field>
        {list.count}
      </div>
      {!list.value ? list.pending
        : list.value.records.length === 0 ? <StatePanel tone="empty" title={t("adminNoRecords")} />
        : (
          <RowList>
            {list.value.records.map((r) => (
              <li key={r.id} className="px-3 py-2">
                <AdminLink to={`/records/${r.id}`}
                  className="font-medium text-fg underline break-words">{r.label}</AdminLink>
                <p className="text-caption text-muted"><span className="font-mono">{r.id}</span>{r.detail
                  && ` · ${r.detail}`}</p>
              </li>
            ))}
          </RowList>
        )}
      {list.pager}
    </section>
  );
};
