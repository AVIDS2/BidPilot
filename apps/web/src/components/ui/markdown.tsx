import { cn } from '@/lib/utils';
import 'katex/dist/katex.min.css';
import { marked } from 'marked';
import { memo, useId, useMemo, type HTMLAttributes } from 'react';
import rehypeKatex from 'rehype-katex';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import { CodeBlock, CodeBlockCode } from './code-block';

export type MarkdownVariant = 'default' | 'typora' | 'assistant';

export type MarkdownProps = Omit<HTMLAttributes<HTMLDivElement>, 'children'> & {
  children: string;
  variant?: MarkdownVariant;
  components?: Partial<Components>;
};

function parseMarkdownIntoBlocks(markdown: string): string[] {
  const tokens = marked.lexer(markdown);
  return tokens.map((token) => token.raw);
}

function extractLanguage(className?: string): string {
  if (!className) return 'plaintext';
  const match = className.match(/language-(\w+)/);
  return match ? match[1] : 'plaintext';
}

const INITIAL_COMPONENTS: Partial<Components> = {
  code: function CodeComponent({ className, children, node, ...props }) {
    const isInline =
      !node?.position?.start.line || node?.position?.start.line === node?.position?.end.line;

    if (isInline) {
      return (
        <span
          className={cn(
            'rounded-md bg-[color-mix(in_oklch,var(--muted)_76%,transparent)] px-1.5 py-0.5 font-mono text-[0.92em] text-foreground',
            className
          )}
          {...props}
        >
          {children}
        </span>
      );
    }

    const language = extractLanguage(className);

    return (
      <CodeBlock className={className}>
        <CodeBlockCode code={children as string} language={language} />
      </CodeBlock>
    );
  },
  pre: function PreComponent({ children }) {
    return <>{children}</>;
  },
  // Keep markdown tables content-sized. Wrapping enables horizontal scroll
  // without stretching the table to 100% of the chat bubble.
  table: function TableComponent({ children, ...props }) {
    return (
      <div className='markdown-table-scroll'>
        <table {...props}>{children}</table>
      </div>
    );
  }
};

const MemoizedMarkdownBlock = memo(
  function MarkdownBlock({
    content,
    components = INITIAL_COMPONENTS
  }: {
    content: string;
    components?: Partial<Components>;
  }) {
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    );
  },
  function propsAreEqual(prevProps, nextProps) {
    return prevProps.content === nextProps.content;
  }
);

MemoizedMarkdownBlock.displayName = 'MemoizedMarkdownBlock';

function MarkdownComponent({
  children,
  id,
  className,
  variant = 'default',
  components = INITIAL_COMPONENTS,
  ...props
}: MarkdownProps) {
  const generatedId = useId();
  const blockId = id ?? generatedId;
  const blocks = useMemo(() => parseMarkdownIntoBlocks(children), [children]);
  const mergedComponents = useMemo(() => ({ ...INITIAL_COMPONENTS, ...components }), [components]);

  return (
    <div
      id={id}
      className={cn(
        variant !== 'default' && 'prose-bidpilot',
        variant === 'typora' && 'prose-bidpilot-typora',
        variant === 'assistant' && 'prose-bidpilot-assistant',
        className
      )}
      data-markdown-variant={variant}
      {...props}
    >
      {blocks.map((block, index) => (
        <MemoizedMarkdownBlock
          key={`${blockId}-block-${index}`}
          content={block}
          components={mergedComponents}
        />
      ))}
    </div>
  );
}

const Markdown = memo(MarkdownComponent);
Markdown.displayName = 'Markdown';

export { Markdown };
