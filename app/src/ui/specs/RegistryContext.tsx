import { createContext, useContext } from "react";
import type { RegistryView } from "../../domain/views.ts";

export type RegistryLabels = Pick<RegistryView, "spec_definitions" | "spec_groups" | "categories" | "pipeline_stages"
  | "domains">;

const RegistryContext = createContext<RegistryLabels>({ spec_definitions: {}, spec_groups: {}, categories: [],
  pipeline_stages: [], domains: [] });

export const RegistryProvider = RegistryContext.Provider;

export function useRegistry(): RegistryLabels {
  return useContext(RegistryContext);
}
