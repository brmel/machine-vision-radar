import { useState, type ChangeEvent, type FC } from "react";
import type { MatchView, SearchHits } from "../../../../domain/views.ts";
import { Button, CONTROL, Field, RowList, formatNumber, localized, prevented,
  useRegistry } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { useAdmin } from "../../model.ts";
import { AdminLink } from "../../useLoad.tsx";

export const QueryConsole: FC<{ onFail: (err: unknown) => void }> = ({ onFail }) => {
  const { search } = useAdmin();
  const { t, locale } = useI18n();
  const { spec_definitions: specs } = useRegistry();
  const why = (w: MatchView) =>
    `${w.key && specs[w.key] ? localized(specs[w.key].label, locale) : w.field}: ${w.terms.join(", ")}`;
  const [query, setQuery] = useState("");
  const [semantic, setSemantic] = useState(false);
  const [hits, setHits] = useState<SearchHits | null>(null);
  const onQuery = (event: ChangeEvent<HTMLInputElement>) => setQuery(event.target.value);
  const onSemantic = (event: ChangeEvent<HTMLInputElement>) => setSemantic(event.target.checked);
  const find = prevented(() => search.query(query, semantic).then(setHits, onFail));
  return (
    <>
      <form onSubmit={find} className="space-y-3">
        <Field label={t("adminConsoleQuery")}><input className={CONTROL} value={query} onChange={onQuery}
          required /></Field>
        <label className="flex items-center gap-2 text-body"><input type="checkbox" checked={semantic}
          onChange={onSemantic} />{t("adminConsoleSemantic")}</label>
        <Button type="submit">{t("adminSearch")}</Button>
      </form>
      {hits && (
        <RowList ordered label={t("adminConsoleHits")}>
          {hits.hits.length === 0 && <li className="p-3 text-body">{t("noMatchingProducts")}</li>}
          {hits.hits.map((h) => (
            <li key={h.id} className="p-3 text-caption space-y-0.5">
              <p>
                <AdminLink to={`/records/${h.id}`}
                  className="font-medium underline">{h.name}</AdminLink> · {h.vendor_name} · {formatNumber(h.score,
                    locale)}
              </p>
              <p className="text-muted">{h.why.map(why).join(" · ")}</p>
            </li>
          ))}
        </RowList>
      )}
    </>
  );
};
