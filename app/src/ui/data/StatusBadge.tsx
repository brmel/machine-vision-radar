import { type FC } from "react";
import type { TermRef } from "../../domain/views.ts";
import { localized } from "../specs/specFormat.ts";
import { Badge, type BadgeTone } from "./Badge.tsx";

const STATUS_TONES: Readonly<Record<string, BadgeTone>> = { active: "positive", announced: "info" };

export const StatusBadge: FC<{ status: TermRef; locale: string; className?: string }> =
  ({ status, locale, className }) => (
  <Badge tone={STATUS_TONES[status.id] ?? "neutral"} className={className}>{localized(status.label, locale)}</Badge>
);
