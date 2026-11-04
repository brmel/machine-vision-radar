import { useCallback, useRef } from "react";
import type { SearchEvent } from "../../../domain/ports/AskApi.ts";
import type { ProductSearch } from "../../../domain/ports/ProductSearch.ts";
import type { Found } from "../../../domain/views.ts";

export function useProductSearch(search: ProductSearch,
    onCounted: (event: SearchEvent) => void): (words: string) => Promise<Found> {
  const last = useRef<{ words: string; result: Promise<Found> } | null>(null);

  return useCallback((words: string): Promise<Found> => {
    if (last.current?.words !== words) {
      const result = search.search(words).then((found) => {
        onCounted("search");
        if (found.products.length === 0) onCounted("zero_result");
        return found;
      }, (err: unknown) => {
        last.current = null;
        throw err;
      });
      last.current = { words, result };
    }
    return last.current.result;
  }, [search, onCounted]);
}
