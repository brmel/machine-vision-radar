import { useState, type FC } from "react";
import type { FeedDeskRow } from "../../../domain/views.ts";
import { LANGUAGES } from "../../../domain/languages.ts";
import { Button, localized } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";
import { useAdmin } from "../model.ts";
import { useProblem, useLoad } from "../useLoad.tsx";

const LINKEDIN = "https://www.linkedin.com/sharing/share-offsite/?url=";

export const ShareActions: FC<{ row: FeedDeskRow }> = ({ row }) => {
  const { news } = useAdmin();
  const { t, locale } = useI18n();
  const shared = useLoad(() => news.shareText(row.id, locale), `share-${row.id}-${locale}`);
  const [copied, setCopied] = useState(false);
  const { alert, refuse: fail } = useProblem("copying a post");
  const copy = (code: string) => () => {
    setCopied(false);
    news.shareText(row.id, code).then((post) => navigator.clipboard.writeText(post.text))
      .then(() => setCopied(true), fail);
  };
  const title = localized(row.title, locale);
  return (
    <div className="flex flex-wrap items-center gap-2">
      {shared.value && (
        <a href={`${LINKEDIN}${encodeURIComponent(shared.value.url)}`} target="_blank" rel="noopener noreferrer"
           className="px-3 py-1.5 rounded-control border border-line text-caption font-medium hover:bg-raised">
          {t("adminNewsShare", { title })}
        </a>
      )}
      {LANGUAGES.filter((l) => row.title[l.code]).map((l) => (
        <Button key={l.code} variant="outline" size="sm" onClick={copy(l.code)}>{t("adminNewsCopy",
          { language: l.label })}</Button>
      ))}
      {copied && <p role="status" className="text-caption text-muted">{t("adminNewsCopied")}</p>}
      {alert}
    </div>
  );
};
