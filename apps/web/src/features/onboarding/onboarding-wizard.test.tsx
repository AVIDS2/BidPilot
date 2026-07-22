import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { OnboardingWizard } from "./onboarding-wizard";

describe("OnboardingWizard", () => {
  it("renders the welcome step first", () => {
    render(<OnboardingWizard />);

    expect(screen.getByText(/Welcome to BidPilot/i)).not.toBeNull();
  });

  it("advances to the create-project step on next", () => {
    render(<OnboardingWizard />);

    fireEvent.click(screen.getByRole("button", { name: /Next/i }));
    expect(screen.getByText(/Create Your First Project/i)).not.toBeNull();
  });

  it("reaches the final step after two advances", () => {
    render(<OnboardingWizard />);

    fireEvent.click(screen.getByRole("button", { name: /Next/i }));
    fireEvent.click(screen.getByRole("button", { name: /Next/i }));
    expect(screen.getByText(/You're All Set/i)).not.toBeNull();
  });

  it("offers the opt-in demo workspace action on the final step", () => {
    const onCreateDemo = vi.fn();
    render(<OnboardingWizard onCreateDemo={onCreateDemo} />);

    fireEvent.click(screen.getByRole("button", { name: /Next/i }));
    fireEvent.click(screen.getByRole("button", { name: /Next/i }));
    fireEvent.click(screen.getByRole("button", { name: /Explore demo workspace/i }));

    expect(onCreateDemo).toHaveBeenCalledOnce();
  });
});
