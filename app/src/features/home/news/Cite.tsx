import type { FC } from "react";
import type { FeedCite } from "../../../domain/views.ts";
import { productPath, vendorPath } from "../../../domain/paths.ts";
import { AppLink, localized } from "../../../ui/index.ts";
import { useI18n } from "../../../shell/i18n/index.tsx";

const LINK = "underline text-fg-secondary hover:text-fg";

interface CiteProps {
  cite: FeedCite;
  onProduct: (slug: string) => void;
  onVendor: (slug: string) => void;
}

export const Cite: FC<CiteProps> = ({ cite, onProduct, onVendor }) => {
  const { locale } = useI18n();
  const { slug } = cite;
  const label = cite.label ?? (cite.type ? localized(cite.type.label, locale) : cite.id);
  if (cite.kind === "product" && slug)
    return <AppLink href={productPath(slug)} onOpen={() => onProduct(slug)} className={LINK}>{label}</AppLink>;
  if (cite.kind === "organization" && slug)
    return <AppLink href={vendorPath(slug)} onOpen={() => onVendor(slug)} className={LINK}>{label}</AppLink>;
  return cite.url ? <a href={cite.url} target="_blank" rel="noopener noreferrer" className={LINK}>{label}</a>
    : <span>{label}</span>;
};
