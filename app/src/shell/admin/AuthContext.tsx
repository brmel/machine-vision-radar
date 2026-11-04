import { createContext, useContext, useEffect, useState, type FC, type ReactNode } from "react";
import type { AuthGateway, AuthUser } from "../../domain/ports/review/AuthGateway.ts";
import { logger } from "../logger.ts";

interface AuthContextValue {
  user: AuthUser | null;
  isConfigured: boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export const AuthProvider: FC<{ children: ReactNode; gateway: AuthGateway }> = ({ children, gateway }) => {
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => gateway.onAuthChange(setUser, (err) => {
    logger.error("admin: the signed-in account's role could not be read", { page: "admin" }, err);
    setUser(null);
  }), [gateway]);

  const value: AuthContextValue = {
    user,
    isConfigured: gateway.isConfigured(),
    signIn: () => gateway.signIn()
      .then(setUser, (err: unknown) => logger.warn("admin: sign-in did not complete", { page: "admin" }, err)),
    signOut: () => gateway.signOut().then(() => setUser(null)),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
