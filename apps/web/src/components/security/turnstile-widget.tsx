import { useEffect, useId, useRef, useState } from "react";

const TURNSTILE_SCRIPT_ID = "cloudflare-turnstile-script";
const TURNSTILE_SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

type TurnstileRenderOptions = {
  sitekey: string;
  action?: string;
  theme?: "light" | "dark" | "auto";
  callback?: (token: string) => void;
  "expired-callback"?: () => void;
  "error-callback"?: () => void;
};

type TurnstileApi = {
  ready: (callback: () => void) => void;
  render: (container: HTMLElement, options: TurnstileRenderOptions) => string;
  reset: (widgetId?: string) => void;
  remove: (widgetId: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

interface TurnstileWidgetProps {
  action: string;
  onTokenChange: (token: string | null) => void;
  onWidgetIdChange?: (widgetId: string | null) => void;
  className?: string;
}

export const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY as string | undefined;

export function isTurnstileConfigured() {
  return Boolean(TURNSTILE_SITE_KEY);
}

export function resetTurnstile(widgetId: string | null) {
  if (widgetId && window.turnstile) {
    window.turnstile.reset(widgetId);
  }
}

export function TurnstileWidget({ action, onTokenChange, onWidgetIdChange, className }: TurnstileWidgetProps) {
  const rawId = useId().replace(/:/g, "");
  const containerRef = useRef<HTMLDivElement | null>(null);
  const widgetIdRef = useRef<string | null>(null);
  const [scriptReady, setScriptReady] = useState(Boolean(window.turnstile));

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY) return;

    const existing = document.getElementById(TURNSTILE_SCRIPT_ID) as HTMLScriptElement | null;
    if (existing) {
      if (window.turnstile) setScriptReady(true);
      existing.addEventListener("load", () => setScriptReady(true), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.id = TURNSTILE_SCRIPT_ID;
    script.src = TURNSTILE_SCRIPT_SRC;
    script.async = true;
    script.addEventListener("load", () => setScriptReady(true), { once: true });
    document.head.appendChild(script);
  }, []);

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY || !scriptReady || !window.turnstile || !containerRef.current) return;
    if (widgetIdRef.current) return;

    let cancelled = false;

    if (cancelled || widgetIdRef.current || !window.turnstile || !containerRef.current) return;

    widgetIdRef.current = window.turnstile.render(containerRef.current, {
      sitekey: TURNSTILE_SITE_KEY,
      action,
      theme: "dark",
      callback: (token) => onTokenChange(token),
      "expired-callback": () => onTokenChange(null),
      "error-callback": () => onTokenChange(null),
    });
    onWidgetIdChange?.(widgetIdRef.current);

    return () => {
      cancelled = true;
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
        widgetIdRef.current = null;
      }
      onWidgetIdChange?.(null);
      onTokenChange(null);
    };
  }, [action, onTokenChange, onWidgetIdChange, scriptReady]);

  if (!TURNSTILE_SITE_KEY) {
    return null;
  }

  return (
    <div className={className}>
      <div id={`turnstile-${rawId}-${action}`} ref={containerRef} />
    </div>
  );
}
