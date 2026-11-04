import type { FC } from "react";
import type { ProposalView } from "../../../../domain/views.ts";
import { formatDate } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { ACTOR, STATUS, kindLabel, useAdmin } from "../../model.ts";
import { AdminLink } from "../../useLoad.tsx";

interface QueueItemProps {
  proposal: ProposalView;
  chosen: boolean;
  onToggle: () => void;
}

export const QueueItem: FC<QueueItemProps> = ({ proposal: p, chosen, onToggle }) => {
  const { model } = useAdmin();
  const { t, plural, locale } = useI18n();
  return (
    <li className="flex items-start gap-3 p-3">
      {p.status === "suggested" && (
        <input type="checkbox" className="mt-1 h-5 w-5" aria-label={t("adminChoose", { id: p.id })} checked={chosen}
          onChange={onToggle} />
      )}
      <div className="min-w-0 flex-1 space-y-0.5">
        <AdminLink to={`/queue/${p.id}`} className="font-medium text-fg underline break-words">
          {kindLabel(model, p.files_on, locale)}: {p.reason || p.message}
        </AdminLink>
        <p className="text-caption text-muted">
          {p.author} · {t(ACTOR[p.actor_kind])} · {formatDate(p.created_at, locale)} · {t(STATUS[p.status])}
          {p.reports > 1 && ` · ${plural("adminReportsOne", "adminReportsOther", p.reports)}`}
        </p>
      </div>
    </li>
  );
};
