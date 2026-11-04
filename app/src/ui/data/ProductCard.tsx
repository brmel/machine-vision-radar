import { type FC } from "react";
import { AppLink } from "../controls/AppLink.tsx";
import { Button } from "../controls/Button.tsx";
import type { ProductCard as CardView } from "../../domain/views.ts";
import { keySpecRows, localized, type SpecValueLabels } from "../specs/specFormat.ts";
import { useRegistry } from "../specs/RegistryContext.tsx";
import { Card } from "../page/Card.tsx";
import { Facts } from "./Facts.tsx";
import { StatusBadge } from "./StatusBadge.tsx";
import { Thumb } from "./Thumb.tsx";

interface Link {
  href: string;
  onOpen: () => void;
}

interface ProductCardProps {
  product: CardView;
  valueLabels: SpecValueLabels;
  link: Link;
  vendorLink?: Link;
  showCategory?: boolean;
  compare?: { label: string; pressed: boolean; disabled: boolean; onToggle: () => void };
}

export const ProductCard: FC<ProductCardProps> = ({ product, valueLabels, link, vendorLink, showCategory = true,
  compare }) => {
  const { spec_definitions: specs, categories } = useRegistry();
  const category = categories.find((c) => c.id === product.category);
  if (!category) throw new Error(`ProductCard: unknown category ${product.category}`);
  return (
    <Card as="article" interactive className="relative flex items-center gap-3 py-2 hover:bg-sunken/60">
      <div className="hidden sm:block"><Thumb url={product.thumbnail_url} glyph={category.glyph} /></div>
      <div className="min-w-0 flex-1">
        <div className="min-w-0 break-words leading-6">
          {vendorLink && <>
            <AppLink href={vendorLink.href} onOpen={vendorLink.onOpen}
              className="relative z-10 text-body text-muted hover:text-fg hover:underline">
              {product.vendor_name}</AppLink>
            <span aria-hidden="true" className="text-faint">{"\u00a0/\u00a0"}</span>
          </>}
          <h3 className="inline text-body font-heading text-fg">
            <AppLink href={link.href} onOpen={link.onOpen}
              className={"after:absolute after:inset-0 after:rounded-card focus-visible:outline-none "
                + "focus-visible:after:ring-2 focus-visible:after:ring-focus"}>
              {product.name.split("/").flatMap((part, n) => (n === 0 ? [part] : ["/", <wbr key={n} />, part]))}
            </AppLink>
          </h3>
        </div>
        <div className="text-caption text-muted leading-5">
          {product.status && <StatusBadge status={product.status} locale={valueLabels.locale} className="mr-2" />}
          {showCategory && <span className="inline-block mr-3">{localized(category.label, valueLabels.locale)}</span>}
          <Facts layout="inline" facts={keySpecRows(product.specs, category.sections.core, specs, valueLabels)} />
        </div>
      </div>
      {compare && (
        <Button variant={compare.pressed ? "secondary" : "outline"} size="sm" aria-pressed={compare.pressed}
          disabled={compare.disabled} onClick={compare.onToggle} className="relative z-10">
          {compare.label}
        </Button>
      )}
    </Card>
  );
};
