import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "./markdown";

describe("Markdown", () => {
  it("renders LaTeX math with KaTeX", () => {
    render(<Markdown>{`$$f'(x_i)=\\frac{f(b)-f(a)}{b-a}$$`}</Markdown>);

    const math = document.querySelector(".katex");
    expect(math).not.toBeNull();
    expect(document.querySelector("annotation[encoding='application/x-tex']")).not.toBeNull();
  });
});
