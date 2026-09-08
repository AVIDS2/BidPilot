import type { ReactNode } from 'react';

const EMBEDDED_URL_PATTERN =
  /(?:mailto:|https?:\/\/)[^\s()[\]{}<>，。；;：、！？“”‘’"'（）【】《》]+/gu;

function decodePercentRuns(value: string) {
  return value.replace(/(?:%[0-9a-f]{2})+(?:%[0-9a-f]{0,1})?/gi, (encoded) => {
    let rest = encoded;
    let decoded = '';
    while (rest) {
      let consumed = false;
      for (let length = rest.length; length >= 3; length -= 3) {
        const candidate = rest.slice(0, length);
        try {
          decoded += decodeURIComponent(candidate);
          rest = rest.slice(length);
          consumed = true;
          break;
        } catch {
          // A truncated UTF-8 sequence should not prevent earlier characters
          // in the same URL from being decoded.
        }
      }
      if (consumed) continue;

      // Drop an incomplete byte fragment rather than exposing replacement
      // characters or a raw percent-encoded tail in the customer UI.
      rest = rest.slice(3);
    }
    return decoded;
  });
}

export function decodeEmbeddedUrls(value: string) {
  return value.replace(EMBEDDED_URL_PATTERN, (candidate) => {
    let decoded = candidate;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const next = decodePercentRuns(decoded);
      if (next === decoded) break;
      decoded = next;
    }
    return decoded.replace(/%[0-9a-f]?/gi, '');
  });
}

export function RequirementText({ value }: { value: string }) {
  const decoded = decodeEmbeddedUrls(value);
  const parts: ReactNode[] = [];
  let cursor = 0;

  for (const match of decoded.matchAll(EMBEDDED_URL_PATTERN)) {
    const url = match[0];
    const start = match.index ?? 0;
    if (start > cursor) parts.push(decoded.slice(cursor, start));
    parts.push(
      <a
        className='text-primary break-all underline underline-offset-2 hover:no-underline'
        href={url}
        key={`${start}-${url}`}
        rel={url.startsWith('http') ? 'noreferrer' : undefined}
        target={url.startsWith('http') ? '_blank' : undefined}
      >
        {url}
      </a>
    );
    cursor = start + url.length;
  }

  if (cursor < decoded.length) parts.push(decoded.slice(cursor));
  return <>{parts}</>;
}
