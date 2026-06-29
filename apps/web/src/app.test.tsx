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
    // 逐字动画把文字拆分成了单独的字符span，使用getAllByText获取所有字符
    const heroChars = screen.getAllByText((content, element) => {
      return element?.textContent?.includes("AI-Powered") || false;
    });
    expect(heroChars.length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /Start Free Trial/i }).length).toBeGreaterThan(0);
  });

  it("renders the signup page without unavailable social auth actions", () => {
    window.history.pushState({}, "", "/signup");
    render(<App />);
    // 注册页面有BidPilot文本（Logo或影视标注）
    const pageContent = document.body.textContent || "";
    expect(pageContent).toContain("BidPilot");
    expect(screen.queryByText(/Sign up with (Apple|Google|Meta)/)).not.toBeInTheDocument();
  });
});
