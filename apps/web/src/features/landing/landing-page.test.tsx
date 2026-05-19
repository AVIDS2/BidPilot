import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { LandingPage } from "./landing-page";

function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
}

describe("LandingPage", () => {
  it("renders the hero headline and sub-headline", () => {
    renderWithRouter(<LandingPage />);

    expect(screen.getByText(/AI-Powered Document Execution/i)).not.toBeNull();
    expect(screen.getByText(/Turn source materials into reviewable/i)).not.toBeNull();
  });

  it("renders three feature highlight cards", () => {
    renderWithRouter(<LandingPage />);

    expect(screen.getByText("Smart Extraction")).not.toBeNull();
    expect(screen.getByText("Evidence-Backed Drafts")).not.toBeNull();
    expect(screen.getByText("Audit Trail")).not.toBeNull();
  });

  it("renders a CTA button linking to signup", () => {
    renderWithRouter(<LandingPage />);

    const cta = screen.getByRole("link", { name: /Get Started/i });
    expect(cta).not.toBeNull();
    expect(cta.getAttribute("href")).toContain("/signup");
  });
});
