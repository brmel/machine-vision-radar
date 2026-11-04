import { type FC, type ReactNode } from "react";
import { TYPE } from "../theme/typography.ts";

interface SectionProps {
  title: ReactNode;
  sub?: boolean;
  note?: ReactNode;
  aside?: ReactNode;
  id?: string;
  className?: string;
  children: ReactNode;
}

export const Section: FC<SectionProps> = ({ title, sub = false, note, aside, id, className = "", children }) => {
  const Heading = sub ? "h3" : "h2";
  return (
    <section aria-labelledby={id} className={`space-y-2 ${className}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4">
        <Heading id={id} className={sub ? TYPE.label : TYPE.section}>{title}</Heading>
        {aside}
      </div>
      {note && <p className="text-caption text-muted">{note}</p>}
      {children}
    </section>
  );
};
