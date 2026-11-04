import { type FC } from "react";
import type { Profile } from "./brand.ts";

interface BrandLinksProps {
  label: string;
  profiles: readonly Profile[];
  addresses?: readonly { label: string; address: string }[];
  className?: string;
}

const LINK = "hover:underline text-fg-secondary";

export const BrandLinks: FC<BrandLinksProps> = ({ label, profiles, addresses = [], className }) => {
  const mail = addresses.filter((a) => a.address);
  const pages = profiles.filter((p) => p.url);
  if (mail.length + pages.length === 0) return null;
  return (
    <ul aria-label={label} className={`flex flex-wrap gap-x-4 gap-y-1 ${className ?? ""}`}>
      {mail.map((a) =>
        <li key={a.label}>{a.label} <a href={`mailto:${a.address}`} className={LINK}>{a.address}</a></li>)}
      {pages.map((p) => <li key={p.network}><a href={p.url} rel="me noopener noreferrer" target="_blank"
        className={LINK}>{p.network}</a></li>)}
    </ul>
  );
};
