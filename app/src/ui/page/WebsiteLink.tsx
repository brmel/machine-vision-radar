import type { FC } from "react";
import { ExternalLink } from "lucide-react";
import { buttonClass } from "../controls/Button.tsx";

export const WebsiteLink: FC<{ href: string; label: string }> = ({ href, label }) => (
  <a href={href} target="_blank" rel="noopener noreferrer" className={buttonClass("outline", "sm")}>
    <span>{label}</span>
    <ExternalLink className="w-3 h-3" aria-hidden="true" />
  </a>
);
