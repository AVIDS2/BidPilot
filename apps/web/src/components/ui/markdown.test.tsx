import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "./markdown";
import { MessageContent } from "./message";

describe("Markdown", () => {
  it("renders LaTeX math with KaTeX", () => {
    render(<Markdown>{`$$f'(x_i)=\\frac{f(b)-f(a)}{b-a}$$`}</Markdown>);

    const math = document.querySelector(".katex");
    expect(math).not.toBeNull();
    expect(document.querySelector("annotation[encoding='application/x-tex']")).not.toBeNull();
  });

  it("applies the BidPilot Typora reading theme", () => {
    render(
      <Markdown variant="typora" data-testid="markdown">
        {"# 标题\n\n正文 `code`"}
      </Markdown>,
    );

    const markdown = screen.getByTestId("markdown");
    expect(markdown.className).toContain("prose-bidpilot");
    expect(markdown.className).toContain("prose-bidpilot-typora");
    expect(markdown.getAttribute("data-markdown-variant")).toBe("typora");
  });

  it("passes the Typora reading theme through MessageContent", () => {
    render(
      <MessageContent markdown variant="typora" data-testid="message-markdown">
        {"BidPilot **draft**"}
      </MessageContent>,
    );

    const message = screen.getByTestId("message-markdown");
    expect(message.className).toContain("prose-bidpilot");
    expect(message.className).toContain("prose-bidpilot-typora");
  });
});
