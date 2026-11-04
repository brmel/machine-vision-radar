import { type FC, type ReactNode } from "react";

export const Field: FC<{ label: string; hint?: string; children: ReactNode; className?: string }> =
  ({ label, hint, children, className = "" }) => (
  <label className={`block space-y-1 ${className}`}>
    <span className="block text-caption font-medium text-fg-secondary">{label}</span>
    {children}
    {hint && <span className="block text-micro text-muted">{hint}</span>}
  </label>
);
