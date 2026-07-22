import { cn } from "@/lib/utils"
import React, { useEffect, useState } from "react"

type SupportedLanguage =
  | "bash"
  | "css"
  | "dotenv"
  | "html"
  | "javascript"
  | "json"
  | "markdown"
  | "powershell"
  | "python"
  | "sql"
  | "tsx"
  | "typescript"
  | "yaml"
type SupportedTheme = "github-dark" | "github-light"
type CodeToHtml = (code: string, options: { lang: SupportedLanguage; theme: SupportedTheme }) => Promise<string>

const languageAliases: Record<string, SupportedLanguage> = {
  bash: "bash",
  css: "css",
  dockerfile: "bash",
  dotenv: "dotenv",
  env: "dotenv",
  html: "html",
  javascript: "javascript",
  js: "javascript",
  json: "json",
  markdown: "markdown",
  md: "markdown",
  powershell: "powershell",
  ps1: "powershell",
  py: "python",
  python: "python",
  shell: "bash",
  sh: "bash",
  sql: "sql",
  ts: "typescript",
  tsx: "tsx",
  typescript: "typescript",
  yaml: "yaml",
  yml: "yaml",
  zsh: "bash",
}

const themeAliases: Record<string, SupportedTheme> = {
  "github-dark": "github-dark",
  "github-dark-default": "github-dark",
  "github-light": "github-light",
  "github-light-default": "github-light",
}

let codeToHtmlPromise: Promise<CodeToHtml> | null = null

function getCodeToHtml() {
  if (!codeToHtmlPromise) {
    const highlighterLoad = Promise.all([
      import("shiki/core"),
      import("shiki/engine/javascript"),
    ]).then(([{ createBundledHighlighter, createSingletonShorthands }, { createJavaScriptRegexEngine }]) => {
      const createHighlighter = createBundledHighlighter({
        // Keep the browser highlighter intentionally narrow. Unsupported code
        // fences remain readable as plain text instead of shipping every grammar.
        langs: {
          bash: () => import("@shikijs/langs/bash"),
          css: () => import("@shikijs/langs/css"),
          dotenv: () => import("@shikijs/langs/dotenv"),
          html: () => import("@shikijs/langs/html"),
          javascript: () => import("@shikijs/langs/javascript"),
          json: () => import("@shikijs/langs/json"),
          markdown: () => import("@shikijs/langs/markdown"),
          powershell: () => import("@shikijs/langs/powershell"),
          python: () => import("@shikijs/langs/python"),
          sql: () => import("@shikijs/langs/sql"),
          tsx: () => import("@shikijs/langs/tsx"),
          typescript: () => import("@shikijs/langs/typescript"),
          yaml: () => import("@shikijs/langs/yaml"),
        },
        themes: {
          "github-dark": () => import("@shikijs/themes/github-dark"),
          "github-light": () => import("@shikijs/themes/github-light"),
        },
        engine: () => createJavaScriptRegexEngine(),
      })

      return createSingletonShorthands(createHighlighter).codeToHtml as CodeToHtml
    })

    codeToHtmlPromise = highlighterLoad.catch((error) => {
      // A transient chunk/network failure must not disable highlighting for the
      // entire tab. Later code blocks can retry while retaining their raw view.
      codeToHtmlPromise = null
      throw error
    })
  }

  return codeToHtmlPromise
}

function resolveLanguage(language: string) {
  return languageAliases[language.trim().toLowerCase().replace(/^language-/, "")]
}

function resolveTheme(theme: string): SupportedTheme {
  return themeAliases[theme.trim().toLowerCase()] ?? "github-light"
}

export type CodeBlockProps = {
  children?: React.ReactNode
  className?: string
} & React.HTMLProps<HTMLDivElement>

function CodeBlock({ children, className, ...props }: CodeBlockProps) {
  return (
    <div
      className={cn(
        "not-prose flex w-full flex-col overflow-clip border",
        "border-border bg-card text-card-foreground rounded-xl",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export type CodeBlockCodeProps = {
  code: string
  language?: string
  theme?: string
  className?: string
} & React.HTMLProps<HTMLDivElement>

function CodeBlockCode({
  code,
  language = "tsx",
  theme = "github-light",
  className,
  ...props
}: CodeBlockCodeProps) {
  const [highlightedHtml, setHighlightedHtml] = useState<string | null>(null)

  useEffect(() => {
    let isCurrent = true

    async function highlight() {
      setHighlightedHtml(null)
      if (!code) {
        if (isCurrent) setHighlightedHtml("<pre><code></code></pre>")
        return
      }

      const resolvedLanguage = resolveLanguage(language)
      if (!resolvedLanguage) return

      try {
        const codeToHtml = await getCodeToHtml()
        const html = await codeToHtml(code, {
          lang: resolvedLanguage,
          theme: resolveTheme(theme),
        })
        if (isCurrent) setHighlightedHtml(html)
      } catch {
        // Raw code remains available if a highlighter chunk cannot be loaded.
      }
    }

    void highlight()
    return () => {
      isCurrent = false
    }
  }, [code, language, theme])

  const classNames = cn(
    "w-full overflow-x-auto text-[13px] [&>pre]:px-4 [&>pre]:py-4",
    className
  )

  // SSR fallback: render plain code if not hydrated yet
  return highlightedHtml ? (
    <div
      className={classNames}
      dangerouslySetInnerHTML={{ __html: highlightedHtml }}
      {...props}
    />
  ) : (
    <div className={classNames} {...props}>
      <pre>
        <code>{code}</code>
      </pre>
    </div>
  )
}

export type CodeBlockGroupProps = React.HTMLAttributes<HTMLDivElement>

function CodeBlockGroup({
  children,
  className,
  ...props
}: CodeBlockGroupProps) {
  return (
    <div
      className={cn("flex items-center justify-between", className)}
      {...props}
    >
      {children}
    </div>
  )
}

export { CodeBlockGroup, CodeBlockCode, CodeBlock }
