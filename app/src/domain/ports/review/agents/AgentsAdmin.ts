import type { AgentTokenList, AgentTokenView, IssuedToken } from "../../../views.ts";

export type TokenRequest = Pick<AgentTokenView, "name" | "scope" | "expires" | "limits">;

export interface AgentsAdmin {
  agentTokens(cursor?: string): Promise<AgentTokenList>;
  issueToken(request: TokenRequest): Promise<IssuedToken>;
  revokeToken(id: string): Promise<AgentTokenView>;
}
