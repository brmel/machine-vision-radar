import type { ResearchRunList, ResearchRunView } from "../../../views.ts";

export type ResearchScope = { readonly product: string } | { readonly maker: string } | { readonly category: string };

export interface ResearchAdmin {
  researchRuns(cursor?: string): Promise<ResearchRunList>;
  researchRun(id: string): Promise<ResearchRunView>;
  startResearch(scope: ResearchScope): Promise<ResearchRunView>;
  cancelResearch(id: string): Promise<ResearchRunView>;
}
