'use client';

// global-error replaces the root layout when it errors, so globals.css is not
// loaded here — styles must be inline and self-contained.
export default function GlobalError({
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang='zh-CN'>
      <body
        style={{
          margin: 0,
          display: 'flex',
          minHeight: '100vh',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'system-ui, sans-serif'
        }}
      >
        <div style={{ textAlign: 'center', padding: '1rem' }}>
          <h1 style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>页面暂时无法打开</h1>
          <p style={{ color: '#6b7280', marginBottom: '1.25rem' }}>
            页面暂时无法打开，请重新加载；如果问题持续存在，请联系管理员。
          </p>
          <button
            onClick={() => reset()}
            style={{
              padding: '0.5rem 1.25rem',
              borderRadius: '0.5rem',
              border: '1px solid #d1d5db',
              background: 'transparent',
              font: 'inherit',
              cursor: 'pointer'
            }}
          >
            重新加载
          </button>
        </div>
      </body>
    </html>
  );
}
