import { useEffect, useState } from "react";
import { save } from "../../shell/root/preferences.ts";
import { MAX_COMPARED, compareQuery, showsOnlyDifferences } from "../../domain/compare.ts";

export const COMPARED_KEY = "machineVisionRadar.comparedIds";

export function useComparedIds(onComparePage: boolean, initial: readonly string[]) {
  const [comparedIds, setComparedIds] = useState<string[]>(() => [...initial]);

  useEffect(() => {
    save(COMPARED_KEY, JSON.stringify(comparedIds), "compare selection not saved; it stays in memory and in the URL");
    if (!onComparePage) return;
    const query = compareQuery(comparedIds, showsOnlyDifferences(window.location.search));
    const target = query ? `/compare?${query}` : "/compare";
    if (window.location.pathname + window.location.search !== target) window.history.replaceState(null, "", target);
  }, [comparedIds, onComparePage]);

  const toggleCompare = (productId: string) =>
    setComparedIds((prev) => (prev.includes(productId) ? prev.filter((id) => id !== productId)
      : prev.length < MAX_COMPARED ? [...prev, productId] : prev));

  return {
    comparedIds,
    setComparedIds,
    toggleCompare,
    clearCompare: () => setComparedIds([]),
  };
}
