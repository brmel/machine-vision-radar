import { createRoot } from "react-dom/client";
import App from "./shell/root/App.tsx";
import { browserStart } from "./shell/root/start.ts";
import "./index.css";

createRoot(document.getElementById("root")!).render(<App start={browserStart()} />);
