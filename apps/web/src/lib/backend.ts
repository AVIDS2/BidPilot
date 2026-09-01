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
