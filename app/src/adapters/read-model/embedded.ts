import type { ProductView } from "../../domain/views.ts";
import { ProductViewSchema } from "../generated-views-zod.ts";

export function embeddedProduct(doc: Document): ProductView | null {
  const text = doc.getElementById("mvr-product")?.textContent;
  return text ? ProductViewSchema.parse(JSON.parse(text)) : null;
}
