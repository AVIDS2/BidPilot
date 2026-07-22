import { render, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"
import { describe, expect, it, vi } from "vitest"

import { CodeBlockCode } from "./code-block"

const codeToHtml = vi.fn().mockResolvedValue('<pre><code data-highlighted="true">const answer = 42</code></pre>')

vi.mock("shiki/core", () => ({
  createBundledHighlighter: vi.fn(() => vi.fn()),
  createSingletonShorthands: vi.fn(() => ({ codeToHtml })),
}))

vi.mock("shiki/engine/javascript", () => ({
  createJavaScriptRegexEngine: vi.fn(),
}))

describe("CodeBlockCode", () => {
  it("loads syntax highlighting on demand and preserves a raw-code fallback", async () => {
    const { container } = render(<CodeBlockCode code="const answer = 42" language="typescript" />)

    expect(container.querySelector("code")?.textContent).toBe("const answer = 42")

    await waitFor(() => {
      expect(container.querySelector("code[data-highlighted='true']")).toBeInTheDocument()
    })
  })
})
