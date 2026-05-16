import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "./app";

describe("App", () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.pushState({}, "", "/");
  });

  it("renders the landing page for unauthenticated users at /", () => {
    render(<App />);
    expect(screen.getByText(/AI-Powered Document Execution/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Get Started/i })).toBeInTheDocument();
  });

  it("renders the signup page without unavailable social auth actions", () => {
    window.history.pushState({}, "", "/signup");
    render(<App />);
    expect(screen.getByRole("heading", { name: "Create your account" })).toBeInTheDocument();
    expect(screen.queryByText(/Sign up with (Apple|Google|Meta)/)).not.toBeInTheDocument();
  });
});
