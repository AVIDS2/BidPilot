import { forwardRef, useCallback, useEffect, useId, useImperativeHandle, useRef, useState } from "react";

const TURNSTILE_SCRIPT_ID = "cloudflare-turnstile-script";
const TURNSTILE_SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

type TurnstileRenderOptions = {
  sitekey: string;
  action?: string;
  appearance?: "always" | "execute" | "interaction-only";
  execution?: "render" | "execute";
  refreshExpired?: "auto" | "manual" | "never";
  theme?: "light" | "dark" | "auto";
  callback?: (token: string) => void;
  "expired-callback"?: () => void;
  "error-callback"?: () => void;
};

type TurnstileApi = {
  ready?: (callback: () => void) => void;
  render: (container: HTMLElement, options: TurnstileRenderOptions) => string;
  execute?: (container: HTMLElement | string, options?: Partial<TurnstileRenderOptions>) => void;
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

export interface TurnstileWidgetHandle {
  execute: () => Promise<string | null>;
  reset: () => void;
}

export const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY as string | undefined;

export function isTurnstileConfigured() {
  return Boolean(TURNSTILE_SITE_KEY);
}

function safelyCallTurnstile(action: () => void) {
  try {
    action();
  } catch {
    // Cloudflare can throw when a route transition already removed the widget.
  }
}

export function resetTurnstile(widgetId: string | null) {
  if (widgetId && window.turnstile) {
    safelyCallTurnstile(() => window.turnstile?.reset(widgetId));
  }
}

export const TurnstileWidget = forwardRef<TurnstileWidgetHandle, TurnstileWidgetProps>(function TurnstileWidget(
  { action, onTokenChange, onWidgetIdChange, className },
  ref,
) {
  const rawId = useId().replace(/:/g, "");
  const containerRef = useRef<HTMLDivElement | null>(null);
  const widgetIdRef = useRef<string | null>(null);
  const currentTokenRef = useRef<string | null>(null);
  const pendingResolveRef = useRef<((token: string | null) => void) | null>(null);
  const pendingTimeoutRef = useRef<number | null>(null);
  const [scriptReady, setScriptReady] = useState(Boolean(window.turnstile));

  const clearPendingTimeout = useCallback(() => {
    if (pendingTimeoutRef.current) {
      window.clearTimeout(pendingTimeoutRef.current);
      pendingTimeoutRef.current = null;
    }
  }, []);

  const resolvePending = useCallback(
    (token: string | null) => {
      if (!pendingResolveRef.current) return;

      const resolve = pendingResolveRef.current;
      pendingResolveRef.current = null;
      clearPendingTimeout();
      resolve(token);
    },
    [clearPendingTimeout],
  );

  const publishToken = useCallback(
    (token: string | null) => {
      currentTokenRef.current = token;
      onTokenChange(token);
      resolvePending(token);
    },
    [onTokenChange, resolvePending],
  );

  const waitForWidget = useCallback(async () => {
    if (!TURNSTILE_SITE_KEY) return false;
    if (window.turnstile && containerRef.current && widgetIdRef.current) return true;

    return new Promise<boolean>((resolve) => {
      const startedAt = Date.now();
      const interval = window.setInterval(() => {
        if (window.turnstile && containerRef.current && widgetIdRef.current) {
          window.clearInterval(interval);
          resolve(true);
          return;
        }
        if (Date.now() - startedAt > 10_000) {
          window.clearInterval(interval);
          resolve(false);
        }
      }, 50);
    });
  }, []);

  const execute = useCallback(async () => {
    if (!TURNSTILE_SITE_KEY) return null;
    if (currentTokenRef.current) return currentTokenRef.current;

    const isReady = await waitForWidget();
    const widgetId = widgetIdRef.current;
    if (!isReady || !window.turnstile?.execute || !widgetId) return null;

    return new Promise<string | null>((resolve) => {
      pendingResolveRef.current = resolve;
      clearPendingTimeout();
      pendingTimeoutRef.current = window.setTimeout(() => {
        pendingResolveRef.current = null;
        pendingTimeoutRef.current = null;
        resolve(null);
      }, 60_000);
      try {
        window.turnstile?.execute?.(widgetId);
      } catch {
        pendingResolveRef.current = null;
        clearPendingTimeout();
        resolve(null);
      }
    });
  }, [clearPendingTimeout, waitForWidget]);

  const reset = useCallback(() => {
    currentTokenRef.current = null;
    if (widgetIdRef.current && window.turnstile) {
      safelyCallTurnstile(() => window.turnstile?.reset(widgetIdRef.current ?? undefined));
    }
    onTokenChange(null);
  }, [onTokenChange]);

  useImperativeHandle(ref, () => ({ execute, reset }), [execute, reset]);

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY) return;

    const markScriptReady = () => {
      setScriptReady(Boolean(window.turnstile));
    };

    if (window.turnstile) {
      markScriptReady();
      return;
    }

    const existing = document.getElementById(TURNSTILE_SCRIPT_ID) as HTMLScriptElement | null;
    if (existing) {
      existing.addEventListener("load", markScriptReady, { once: true });
      return () => existing.removeEventListener("load", markScriptReady);
    }

    const script = document.createElement("script");
    script.id = TURNSTILE_SCRIPT_ID;
    script.src = TURNSTILE_SCRIPT_SRC;
    script.async = true;
    script.addEventListener("load", markScriptReady, { once: true });
    document.head.appendChild(script);

    return () => script.removeEventListener("load", markScriptReady);
  }, []);

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY || !scriptReady || !window.turnstile || !containerRef.current) return;
    if (widgetIdRef.current) return;

    try {
      widgetIdRef.current = window.turnstile.render(containerRef.current, {
        sitekey: TURNSTILE_SITE_KEY,
        action,
        appearance: "interaction-only",
        execution: "execute",
        refreshExpired: "auto",
        theme: "auto",
        callback: (token) => publishToken(token),
        "expired-callback": () => publishToken(null),
        "error-callback": () => publishToken(null),
      });
      onWidgetIdChange?.(widgetIdRef.current);
    } catch {
      widgetIdRef.current = null;
      onWidgetIdChange?.(null);
      publishToken(null);
      return;
    }

    return () => {
      const widgetId = widgetIdRef.current;
      widgetIdRef.current = null;
      currentTokenRef.current = null;

      if (widgetId && window.turnstile) {
        safelyCallTurnstile(() => window.turnstile?.remove(widgetId));
      }
      onWidgetIdChange?.(null);
      clearPendingTimeout();
      resolvePending(null);
    };
  }, [action, clearPendingTimeout, onWidgetIdChange, publishToken, resolvePending, scriptReady]);

  if (!TURNSTILE_SITE_KEY) {
    return null;
  }

  return (
    <div className={className}>
      <div id={`turnstile-${rawId}-${action}`} ref={containerRef} />
    </div>
  );
});
