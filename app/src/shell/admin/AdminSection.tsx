import { useMemo, type FC } from "react";
import { FirebaseAuthGateway, type FirebaseWebConfig } from "../../adapters/review/FirebaseAuthGateway.ts";
import { HttpAdminApi } from "../../adapters/review/HttpAdminApi.ts";
import { AdminView } from "./AdminView.tsx";
import { AuthProvider } from "./AuthContext.tsx";
import { RequireAdmin } from "./RequireAdmin.tsx";

function webConfig(): FirebaseWebConfig | null {
  const env = import.meta.env;
  const [apiKey, authDomain, projectId, appId] =
    [env.VITE_FIREBASE_API_KEY, env.VITE_FIREBASE_AUTH_DOMAIN, env.VITE_FIREBASE_PROJECT_ID, env.VITE_FIREBASE_APP_ID];
  if (!apiKey || !authDomain || !projectId || !appId) return null;
  return { apiKey, authDomain, projectId, appId,
    ...(env.VITE_FIREBASE_AUTH_EMULATOR ? { emulator: env.VITE_FIREBASE_AUTH_EMULATOR } : {}) };
}

const AdminSection: FC<{ path: string;
  onNavigate: (path: string, replace?: boolean) => void }> = ({ path, onNavigate }) => {
  const gateway = useMemo(() => new FirebaseAuthGateway(webConfig()), []);
  const api = useMemo(() => new HttpAdminApi(() => gateway.idToken()), [gateway]);
  return (
    <AuthProvider gateway={gateway}>
      <RequireAdmin>
        <AdminView api={api} path={path} onNavigate={onNavigate} />
      </RequireAdmin>
    </AuthProvider>
  );
};

export default AdminSection;
