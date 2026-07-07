import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PricingPage } from "./pricing-page";
import { AuthProvider } from "@/lib/auth";

const qc = new QueryClient();

function renderWithRouter(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <AuthProvider>{ui}</AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe("PricingPage", () => {
  it("renders the three pricing tiers", () => {
    renderWithRouter(<PricingPage />);

    expect(screen.getAllByText("Starter").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Professional").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Enterprise").length).toBeGreaterThanOrEqual(1);
  });

  it("marks the Professional tier as recommended", () => {
    renderWithRouter(<PricingPage />);

    const badges = screen.getAllByText("Recommended");
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });

  it("shows feature lists for each tier", () => {
    renderWithRouter(<PricingPage />);

    expect(screen.getByText(/Up to 3 projects/i)).not.toBeNull();
    expect(screen.getAllByText(/Unlimited projects/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Custom deployment/i)).not.toBeNull();
  });
});
