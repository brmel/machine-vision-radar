import { type ReactElement } from "react";
import type { LucideIcon } from "lucide-react";
import { Badge } from "../data/Badge.tsx";

interface Segment<T extends string> {
  readonly id: T;
  readonly label: string;
  readonly icon?: LucideIcon;
  readonly lang?: string;
  readonly title?: string;
  readonly count?: number;
}

const LOOKS = {
  pill: {
    group: "inline-flex items-center p-0.5 rounded-control border border-line-strong bg-raised text-caption",
    option: "justify-center rounded-chip font-medium",
    text: "px-2 py-1",
    icon: "p-1.5",
    on: "bg-surface text-fg shadow-control",
    off: "text-muted hover:text-fg",
  },
  tab: {
    group: "flex items-center gap-1 border-b border-line",
    option: "text-body font-medium whitespace-nowrap border-b-2",
    text: "px-3 py-2",
    icon: "p-2",
    on: "border-accent text-fg",
    off: "border-transparent text-muted hover:text-fg",
  },
} as const;

interface SegmentedProps<T extends string> {
  label: string;
  options: readonly Segment<T>[];
  value: T;
  onChange: (id: T) => void;
  look?: keyof typeof LOOKS;
}

export const Segmented =
  <T extends string>({ label, options, value, onChange, look = "pill" }: SegmentedProps<T>): ReactElement => {
  const style = LOOKS[look];
  return (
    <div role="group" aria-label={label} className={style.group}>
      {options.map(({ id, label: name, icon: Icon, lang, title, count }) => (
        <button
          key={id}
          type="button"
          aria-pressed={id === value}
          aria-label={Icon ? name : undefined}
          title={title ?? (Icon ? name : undefined)}
          lang={lang}
          onClick={() => onChange(id)}
          className={`inline-flex items-center gap-1.5 transition-colors cursor-pointer ${Icon ? style.icon
            : style.text} ${style.option} ${id === value ? style.on : style.off}`}
        >
          {Icon ? <Icon className="w-3.5 h-3.5" aria-hidden="true" /> : name}
          {count !== undefined && <Badge>{count}</Badge>}
        </button>
      ))}
    </div>
  );
};
