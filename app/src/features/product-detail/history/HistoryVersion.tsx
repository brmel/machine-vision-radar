import type { FC } from "react";
import { ArrowRight } from "lucide-react";
import { DEFAULT_LANGUAGE } from "../../../domain/languages.ts";
import type { FieldChangeView, HistoryEntry } from "../../../domain/views.ts";
import { Badge, Facts, SourceChip, formatDate, specRowLabel, useRegistry } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";

export const HistoryVersion: FC<{ version: HistoryEntry; productId: string }> = ({ version: v, productId }) => {
  const { t, locale } = useI18n();
  const { spec_definitions: specs } = useRegistry();
  const actor: Record<HistoryEntry["actor_kind"], string> =
    { human: t("historyActor_human"), agent: t("historyActor_agent"), import: t("historyActor_import") };
  const field = (path: string) =>
    (path.split(".")[0] in specs ? specRowLabel(path.split(".")[0], specs, locale) : path);
  const version = t("historyVersion", { version: v.version });
  const heading = v.entity === productId ? version
    : `${v.spec && v.spec in specs ? specRowLabel(v.spec, specs, locale) : v.spec ?? v.entity} · ${version}`;
  const change = (c: FieldChangeView) => (
    <span className="font-mono wrap-anywhere">
      <span className="line-through text-muted">{c.before ?? t("historyNone")}</span> <ArrowRight
        className="inline w-3 h-3" aria-hidden="true" /> <span>{c.after ?? t("historyNone")}</span>
    </span>
  );
  return (
    <li className="p-3 space-y-1.5">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted">
        <span className="font-semibold text-fg">{heading}</span>
        <span className="tabular-nums">{formatDate(v.recorded_at, locale)}</span>
        <Badge>{actor[v.actor_kind]}</Badge>
      </p>
      <p lang={DEFAULT_LANGUAGE.code} className="text-body text-fg break-words">{v.reason}</p>
      <Facts layout="grid" className="text-caption"
        facts={v.changed.map((c) => ({ key: c.path, label: field(c.path), value: change(c) }))} />
      {v.sources.length > 0 && (
        <p className="flex flex-wrap items-center gap-1.5 text-caption text-muted">
          <span>{t("historySources")}</span>
          {v.sources.map((s) => <SourceChip key={s.id} source={s} locale={locale} />)}
        </p>
      )}
    </li>
  );
};
