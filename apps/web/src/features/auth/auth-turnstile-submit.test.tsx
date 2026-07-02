import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "./login-page";
import { SignupPage } from "./signup-page";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    login: vi.fn(),
    register: vi.fn(),
    token: null,
  }),
}));

vi.mock("@/components/security/turnstile-widget", () => ({
  TurnstileWidget: () => <div data-testid="turnstile-widget" />,
  isTurnstileConfigured: () => true,
  resetTurnstile: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

function renderAuthPage(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("auth pages with Turnstile", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("keeps the login submit button clickable while Turnstile token is pending", async () => {
    renderAuthPage(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "ZHANGtao788@" } });

    expect(screen.getByRole("button", { name: /login/i })).not.toBeDisabled();
  });

  it("keeps the signup submit button clickable while Turnstile token is pending", async () => {
    renderAuthPage(<SignupPage />);

    fireEvent.change(screen.getByLabelText(/display name/i), { target: { value: "Test User" } });
    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText(/organization name/i), { target: { value: "Test Org" } });
    fireEvent.change(screen.getByLabelText(/organization slug/i), { target: { value: "test-org" } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: "ZHANGtao788@" } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: "ZHANGtao788@" } });

    expect(screen.getByRole("button", { name: /create account/i })).not.toBeDisabled();
  });
});
