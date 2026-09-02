import 'server-only';

import { cookies } from 'next/headers';

const ACCESS_COOKIE = 'bidpilot_access_token';
const BACKEND_URL = (
  process.env.DOCPILOT_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  'http://127.0.0.1:8000'
).replace(/\/$/, '');

const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'content-length',
  'host',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade'
]);

// Node fetch transparently decompresses upstream responses. Forwarding the
// original compression metadata would make the browser try to decompress an
// already-decoded body, especially on Cloudflare-proxied JSON and SSE routes.
const RESPONSE_HEADERS_TO_STRIP = new Set([...HOP_BY_HOP_HEADERS, 'content-encoding']);

/**
 * Local `next start` is also production mode, but it is normally served over
 * plain HTTP. Base the cookie flag on the request/proxy protocol so local
 * sessions work without weakening HTTPS deployments.
 */
export function shouldUseSecureCookies(request: Request) {
  const forwardedProto = request.headers.get('x-forwarded-proto')?.split(',')[0]?.trim();
  if (forwardedProto) return forwardedProto.toLowerCase() === 'https';

  try {
    if (new URL(request.url).protocol === 'https:') return true;
  } catch {
    // Fall through to the configured public origin.
  }

  try {
    return new URL(process.env.NEXT_PUBLIC_APP_URL ?? '').protocol === 'https:';
  } catch {
    return false;
  }
}

export async function requestBackend(path: string, init: RequestInit = {}, includeAuth = true) {
  const headers = new Headers(init.headers);
  for (const name of HOP_BY_HOP_HEADERS) headers.delete(name);

  if (includeAuth) {
    const token = (await cookies()).get(ACCESS_COOKIE)?.value;
    if (token) headers.set('Authorization', `Bearer ${token}`);
  }

  return fetch(`${BACKEND_URL}${path}`, {
    ...init,
    headers,
    cache: 'no-store'
  });
}

export function forwardBackendResponse(
  upstream: Response,
  options: { cacheControl?: string } = {}
) {
  const headers = new Headers(upstream.headers);
  for (const name of RESPONSE_HEADERS_TO_STRIP) headers.delete(name);
  if (options.cacheControl) headers.set('Cache-Control', options.cacheControl);

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers
  });
}

export async function unavailableResponse() {
  return Response.json(
    {
      code: 'backend_unavailable',
      error: 'backend_unavailable',
      message: '服务暂时不可用，请稍后重试。',
      details: null,
      request_id: null,
      detail: '服务暂时不可用，请稍后重试。'
    },
    { status: 503, headers: { 'Cache-Control': 'no-store' } }
  );
}

export { ACCESS_COOKIE };
