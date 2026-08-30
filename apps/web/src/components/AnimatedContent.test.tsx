import { render } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { describe, expect, it } from "vitest";

import AnimatedContent from "./AnimatedContent";

describe("AnimatedContent", () => {
  it("does not leak animation-only props into the DOM", () => {
    const { container } = render(
      <AnimatedContent direction="horizontal" reverse duration={0.8}>
        Content
      </AnimatedContent>,
    );

    const element = container.firstElementChild;
    expect(element).not.toHaveAttribute("reverse");
    expect(element).not.toHaveAttribute("direction");
    expect(element).not.toHaveAttribute("duration");
    expect(element).toHaveTextContent("Content");
  });
});
