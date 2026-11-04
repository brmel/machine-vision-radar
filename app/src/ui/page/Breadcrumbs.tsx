import { type FC } from "react";
import { AppLink } from "../controls/AppLink.tsx";

export interface Crumb {
  readonly label: string;
  readonly href: string;
  readonly onOpen: () => void;
}

export const Breadcrumbs: FC<{ label: string; trail: readonly Crumb[] }> = ({ label, trail }) => (
  <nav aria-label={label} className="text-caption text-muted">
    <ol className="flex flex-wrap items-center gap-x-1.5">
      {trail.map((crumb, n) => (
        <li key={crumb.href} className="flex items-center gap-x-1.5">
          {n > 0 && <span aria-hidden="true" className="text-faint">/</span>}
          <AppLink href={crumb.href} onOpen={crumb.onOpen}
            className="hover:text-fg hover:underline">{crumb.label}</AppLink>
        </li>
      ))}
    </ol>
  </nav>
);
