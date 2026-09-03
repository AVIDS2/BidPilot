import 'server-only';

import { cookies } from 'next/headers';

const ACCESS_COOKIE = 'bidpilot_access_token';
const REFRESH_COOKIE = 'bidpilot_refresh_token';
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

type SessionRenewal =
  | { accessToken: string }
  | { response: Response }
  | null;

type RefreshResult =
  | { ok: true; accessToken: string; refreshToken?: string | null }
  | { ok: false; status: number; body: string };

const REFRESH_RESULT_GRACE_MS = 5_000;
let refreshInFlight: { token: string; promise: Promise<RefreshResult> } | null = null;
let lastRefreshResult: {
  token: string;
  result: Extract<RefreshResult, { ok: true }>;
  expiresAt: number;
} | null = null;

async function refreshFromBackend(refreshToken: string): Promise<RefreshResult> {
  const upstream = await requestBackend(
    '/auth/refresh',
    {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    },
    false
  );
  const body = await upstream.text().catch(() => '');
  if (!upstream.ok) return { ok: false, status: upstream.status, body };

  let payload: { access_token?: string; refresh_token?: string | null };
  try {
    payload = JSON.parse(body) as { access_token?: string; refresh_token?: string | null };
  } catch {
    return { ok: false, status: 502, body: JSON.stringify({ message: '刷新响应不是有效 JSON。' }) };
  }
  if (!payload.access_token) {
    return { ok: false, status: 502, body: JSON.stringify({ message: '刷新响应缺少访问令牌。' }) };
  }
  return { ok: true, accessToken: payload.access_token, refreshToken: payload.refresh_token };
}

/** Renew a browser session without exposing tokens to the client bundle. */
export async function renewSession(request: Request): Promise<SessionRenewal> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(REFRESH_COOKIE)?.value;
  if (!refreshToken) return null;

  const existing = refreshInFlight;
  const cached =
    lastRefreshResult?.token === refreshToken && lastRefreshResult.expiresAt > Date.now()
      ? lastRefreshResult.result
      : null;
  const promise = existing?.token === refreshToken
    ? existing.promise
    : cached
      ? Promise.resolve(cached)
      : refreshFromBackend(refreshToken);
  if (!existing || existing.token !== refreshToken) {
    if (!cached) {
      refreshInFlight = { token: refreshToken, promise };
      void promise
        .then((result) => {
          if (result.ok) {
            lastRefreshResult = {
              token: refreshToken,
              result,
              expiresAt: Date.now() + REFRESH_RESULT_GRACE_MS
            };
          }
        })
        .finally(() => {
          if (refreshInFlight?.promise === promise) refreshInFlight = null;
        })
        .catch(() => undefined);
    }
  }
  const result = await promise;
  if (!result.ok) {
    // A rejected refresh is terminal. Temporary upstream errors must preserve
    // the cookies so a later request can retry instead of logging the user out.
    if (result.status === 401 || result.status === 403) {
      cookieStore.delete(ACCESS_COOKIE);
      cookieStore.delete(REFRESH_COOKIE);
    }
    let failureBody: unknown = { message: '刷新失败。' };
    if (result.body) {
      try {
        failureBody = JSON.parse(result.body) as unknown;
      } catch {
        failureBody = { message: result.body };
      }
    }
    return {
      response: Response.json(failureBody, {
        status: result.status,
        headers: { 'Cache-Control': 'no-store' }
      })
    };
  }

  const secure = shouldUseSecureCookies(request);
  cookieStore.set(ACCESS_COOKIE, result.accessToken, {
    httpOnly: true,
    sameSite: 'lax',
    secure,
    path: '/',
    maxAge: 60 * 60
  });
  if (result.refreshToken) {
    cookieStore.set(REFRESH_COOKIE, result.refreshToken, {
      httpOnly: true,
      sameSite: 'lax',
      secure,
      path: '/',
      maxAge: 60 * 60 * 24 * 30
    });
  }
  return { accessToken: result.accessToken };
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

export { ACCESS_COOKIE, REFRESH_COOKIE };
