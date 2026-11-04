import type { FC } from "react";
import type { BundleMember } from "../../../../domain/views.ts";
import { Badge } from "../../../../ui/index.ts";
import { useI18n } from "../../../../shell/i18n/index.tsx";
import { RISK, STATUS, kindLabel, useAdmin } from "../../model.ts";
import { AdminLink } from "../../useLoad.tsx";

interface BundleItemProps {
  member: BundleMember;
  left: boolean;
  onToggle: () => void;
}

export const BundleItem: FC<BundleItemProps> = ({ member: { proposal: p, risk, after }, left, onToggle }) => {
  const { model } = useAdmin();
  const { t, locale } = useI18n();
  return (
    <li className="flex items-start gap-3 p-3">
      {p.status === "suggested" && (
        <input type="checkbox" className="mt-1 h-5 w-5" aria-label={t("adminLeaveOut", { id: p.id })}
          checked={left} onChange={onToggle} />
      )}
      <div className="min-w-0 flex-1 space-y-0.5">
        <AdminLink to={`/queue/${p.id}`} className="font-medium text-fg underline break-words">
          {kindLabel(model, p.files_on, locale)}: {p.reason}
        </AdminLink>
        <p className="text-caption text-muted flex flex-wrap items-center gap-x-2">
          {risk && <Badge tone={RISK[risk][1]}>{t(RISK[risk][0])}</Badge>}
          <span>{t(STATUS[p.status])}</span>
          {after.length > 0
            && <span className="font-mono break-all">{t("adminAfter", { ids: after.join(", ") })}</span>}
        </p>
      </div>
    </li>
  );
};
