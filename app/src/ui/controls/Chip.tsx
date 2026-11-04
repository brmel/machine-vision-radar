import { type FC, type ButtonHTMLAttributes } from "react";

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active: boolean;
  label: string;
  count?: number;
}

export const Chip: FC<ChipProps> = ({ active, label, count, className = "", children, ...props }) => (
  <button
    type="button"
    className={`inline-flex items-center gap-1.5 px-2 py-1 text-caption text-left rounded-control font-medium `
      + `transition-colors cursor-pointer ${
      active
        ? "bg-inverse text-on-inverse hover:bg-inverse-hover"
        : "bg-raised text-fg-secondary hover:bg-raised-hover"
    } ${className}`}
    {...props}
  >
    <span className="break-words">{label}</span>
    {count !== undefined && (
      <span className={`text-micro font-mono tabular-nums ${active ? "" : "text-muted"}`}>{count}</span>
    )}
    {children}
  </button>
);
