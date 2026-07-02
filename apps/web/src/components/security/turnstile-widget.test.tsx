import { render, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { describe, expect, it, vi, beforeEach } from "vitest";

describe("turnstile widget", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    document.head.innerHTML = "";
    document.body.innerHTML = "";
    vi.spyOn(document.head, "appendChild").mockImplementation((node: Node) => node as Node & ChildNode);
    window.turnstile = undefined;
  });

  it("does not render when site key is missing", async () => {
    vi.stubEnv("VITE_TURNSTILE_SITE_KEY", "");
    const { TurnstileWidget } = await import("./turnstile-widget");

    render(<TurnstileWidget action="login" onTokenChange={() => {}} />);

    expect(document.querySelector('[id^="turnstile-"]')).toBeNull();
  });

  it("renders a container when site key is configured", async () => {
    vi.stubEnv("VITE_TURNSTILE_SITE_KEY", "site-key");
    const { TurnstileWidget } = await import("./turnstile-widget");

    render(<TurnstileWidget action="login" onTokenChange={() => {}} />);

    expect(document.querySelector('[id^="turnstile-"]')).toBeTruthy();
  });

  it("renders directly after the script API is available without calling turnstile.ready", async () => {
    vi.stubEnv("VITE_TURNSTILE_SITE_KEY", "site-key");
    const ready = vi.fn(() => {
      throw new Error("turnstile.ready should not be called");
    });
    const renderWidget = vi.fn(() => "widget-id");
    const remove = vi.fn();
    const reset = vi.fn();
    window.turnstile = { ready, render: renderWidget, remove, reset };

    const { TurnstileWidget } = await import("./turnstile-widget");

    render(<TurnstileWidget action="login" onTokenChange={() => {}} />);

    await waitFor(() => expect(renderWidget).toHaveBeenCalledTimes(1));
    expect(ready).not.toHaveBeenCalled();
  });
});
