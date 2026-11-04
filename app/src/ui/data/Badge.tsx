import { type FC, type ReactNode } from "react";

const TONES = {
  neutral: "bg-raised text-fg-secondary border-line",
  positive: "bg-success-bg text-success border-success-line",
  info: "bg-info-bg text-info border-info-line",
  warning: "bg-warning-bg text-warning border-warning-line",
  accent: "bg-accent text-on-accent border-accent font-semibold",
} as const;

export type BadgeTone = keyof typeof TONES;

interface BadgeProps {
  tone?: BadgeTone;
  className?: string;
  children: ReactNode;
}

export const Badge: FC<BadgeProps> = ({ tone = "neutral", className = "", children }) => (
  <span className={`inline-flex items-center px-1.5 py-px rounded-full border text-micro font-medium tabular-nums `
    + `whitespace-nowrap ${TONES[tone]} ${className}`}>
    {children}
  </span>
);
