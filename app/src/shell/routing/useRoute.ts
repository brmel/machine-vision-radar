import { useEffect, useState } from "react";
import type { Route } from "./routes.ts";
import { pathFromRoute, routeFromPath } from "./router.ts";

const currentRoute = (): Route => routeFromPath(window.location.pathname, window.location.search);

export function useRoute(initial: Route) {
  const [route, setRoute] = useState<Route>(initial);

  useEffect(() => {
    if (initial.name === "category" && !window.location.pathname.startsWith("/category/"))
      window.history.replaceState(null, "", pathFromRoute(initial));
    const onPopState = () => setRoute(currentRoute());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (nextRoute: Route, replace = false) => {
    setRoute(nextRoute);
    const targetPath = pathFromRoute(nextRoute);
    if (window.location.pathname + window.location.search === targetPath) return;
    if (replace) window.history.replaceState(null, "", targetPath);
    else window.history.pushState(null, "", targetPath);
  };

  return { route, navigate };
}
