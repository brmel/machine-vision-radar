import type { Found } from "../views.ts";

export interface ProductSearch {
  search(words: string): Promise<Found>;
}
