import { type FC, type ReactNode } from "react";
import { useAuth } from "./AuthContext.tsx";
import { useI18n } from "../i18n/index.tsx";
import { StatePanel } from "../../ui/index.ts";

export const RequireAdmin: FC<{ children: ReactNode }> = ({ children }) => {
  const { user, isConfigured, signIn, signOut } = useAuth();
  const { t } = useI18n();
  if (!isConfigured) return <StatePanel tone="empty" level={1} title={t("authNotConfigured")}
    description={t("authNotConfiguredHint")} />;
  if (!user) {
    return <StatePanel tone="empty" level={1} title={t("navAdmin")} description={t("authSignInPrompt")}
      action={{ label: t("authSignInButton"), onClick: () => void signIn() }} />;
  }
  if (user.role !== "admin") {
    return <StatePanel tone="empty" level={1} title={t("authDeniedTitle")} description={t("authNotAuthorized")}
      action={{ label: t("authSignOut"), onClick: () => void signOut() }} />;
  }
  return <>{children}</>;
};
