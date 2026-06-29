import React, { Suspense } from "react";
import ReactDOM from "react-dom/client";
import "./lib/i18n";
import "@xyflow/react/dist/style.css";
import "./index.css";
import { App } from "./app";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Suspense fallback={<div className="flex min-h-svh items-center justify-center text-muted-foreground">Loading...</div>}>
      <App />
    </Suspense>
  </React.StrictMode>,
);
