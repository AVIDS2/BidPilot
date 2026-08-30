import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBoundary } from "./error-boundary";

function ThrowError() {
  throw new Error("Test error");
  return null;
}

function NoError({ text = "Hello World" }: { text?: string }) {
  return <p>{text}</p>;
}

describe("ErrorBoundary", () => {
  it("renders children when no error", () => {
    render(
      <ErrorBoundary>
        <NoError />
      </ErrorBoundary>
    );
    expect(screen.getByText("Hello World")).toBeDefined();
  });

  it("renders fallback UI when error occurs", () => {
    // Suppress console.error for expected error
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );
    expect(screen.getByText("Something went wrong")).toBeDefined();
    spy.mockRestore();
  });

  it("hides a stale chunk URL behind the localized recovery message", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <ThrowChunkError />
      </ErrorBoundary>,
    );
    expect(screen.getByText("This page was updated. Reload it to continue.")).toBeDefined();
    expect(screen.queryByText(/assets\/project-workspace/)).toBeNull();
    spy.mockRestore();
  });

  it("renders custom fallback when provided", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary fallback={<p>Custom Error UI</p>}>
        <ThrowError />
      </ErrorBoundary>
    );
    expect(screen.getByText("Custom Error UI")).toBeDefined();
    spy.mockRestore();
  });
});

function ThrowChunkError(): null {
  throw new Error(
    "Failed to fetch dynamically imported module: https://bidpilot.example/assets/project-workspace-page-old.js",
  );
}
