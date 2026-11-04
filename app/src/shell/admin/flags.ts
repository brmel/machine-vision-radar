import { lazy } from "react";

export const ENABLE_ADMIN = import.meta.env?.VITE_ENABLE_ADMIN === "true";

export const LazyAdminSection = ENABLE_ADMIN ? lazy(() => import("./AdminSection.tsx")) : null;
