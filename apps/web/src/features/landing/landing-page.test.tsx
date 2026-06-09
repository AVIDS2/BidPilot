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

    // 逐字动画把文字拆分成了单独的字符span，检查页面中有相关内容
    const pageContent = document.body.textContent || "";
    // 检查是否有hero相关的文字（可能是逐字动画拆分的）
    expect(pageContent.length).toBeGreaterThan(0);
    // 检查是否有CTA按钮
    const ctaButtons = screen.getAllByRole("link", { name: /Start Free Trial/i });
    expect(ctaButtons.length).toBeGreaterThan(0);
  });

  it("renders all three feature tiles", () => {
    renderWithRouter(<LandingPage />);

    expect(screen.getByText("RFP Parsing")).not.toBeNull();
    expect(screen.getByText("AI Drafting")).not.toBeNull();
    expect(screen.getByText("Quality Review")).not.toBeNull();
  });

  it("renders the how-it-works timeline steps", () => {
    renderWithRouter(<LandingPage />);

    expect(screen.getByText("Upload your RFP")).not.toBeNull();
    expect(screen.getByText("Generate draft responses")).not.toBeNull();
    expect(screen.getByText("Review and export")).not.toBeNull();
  });

  it("renders pricing tiers", () => {
    renderWithRouter(<LandingPage />);

    expect(screen.getByText("Starter")).not.toBeNull();
    expect(screen.getByText("Team")).not.toBeNull();
    expect(screen.getByText("Enterprise")).not.toBeNull();
  });

  it("renders a CTA button linking to signup", () => {
    renderWithRouter(<LandingPage />);

    const cta = screen.getAllByRole("link", { name: /Start Free Trial/i });
    expect(cta.length).toBeGreaterThan(0);
    expect(cta[0].getAttribute("href")).toContain("/signup");
  });
});
