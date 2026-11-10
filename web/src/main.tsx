import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

/* Report any crash to the local server so it lands in watcher.log.
   Dev aid: without this, a blank page gives no clue what threw. */
function reportError(kind: string, err: unknown) {
  const detail =
    err instanceof Error
      ? `${err.message}\n${err.stack ?? ""}`
      : typeof err === "string"
        ? err
        : JSON.stringify(err);
  try {
    fetch("/client-log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, detail: detail.slice(0, 4000), url: location.href }),
    }).catch(() => {});
  } catch {
    /* nothing else to do */
  }
  console.error(`[${kind}]`, err);
}
window.addEventListener("error", (e) => reportError("error", e.error ?? e.message));
window.addEventListener("unhandledrejection", (e) => reportError("unhandledrejection", e.reason));

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
