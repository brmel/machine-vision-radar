import { type FC, type ReactNode } from "react";
import { TYPE } from "../theme/typography.ts";

interface PageHeaderProps {
  title: ReactNode;
  count?: ReactNode;
  media?: ReactNode;
  lead?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}

export const PageHeader: FC<PageHeaderProps> = ({ title, count, media, lead, actions, children }) => (
  <header className="flex flex-col sm:flex-row sm:items-start justify-between gap-x-6 gap-y-2">
    <div className="flex items-start gap-3 min-w-0">
      {media && <div className="hidden sm:block">{media}</div>}
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <h1 className={TYPE.title}>{title}</h1>
          {count && (
            <>
              <span aria-hidden="true" className="text-faint">·</span>
              <span className="text-body font-mono tabular-nums text-muted">{count}</span>
            </>
          )}
        </div>
        {children}
        {lead && <div className="text-body text-fg-secondary max-w-3xl">{lead}</div>}
      </div>
    </div>
    {actions && <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>}
  </header>
);
