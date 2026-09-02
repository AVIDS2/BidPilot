import {
  forwardBackendResponse,
  requestBackend,
  ACCESS_COOKIE,
  shouldUseSecureCookies,
  unavailableResponse
} from '@/lib/backend';
import { cookies } from 'next/headers';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  try {
    const upstream = await requestBackend(
      '/auth/login',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: await request.text()
      },
      false
    );
    if (!upstream.ok) return forwardBackendResponse(upstream);

    const payload = (await upstream.json()) as {
      access_token?: string;
      refresh_token?: string | null;
    };
    if (!payload.access_token)
      return Response.json({ message: '登录响应缺少访问令牌。' }, { status: 502 });

    // Verify the newly issued session before telling the browser that login
    // completed. This prevents a successful token exchange followed by a
    // misleading client-side "cannot read account" state.
    const session = await requestBackend(
      '/auth/me',
      {
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${payload.access_token}`
        }
      },
      false
    );
    if (!session.ok) {
      return Response.json(
        {
          code: 'session_verification_failed',
          message: '登录凭据已签发，但账户信息校验失败，请重新登录。',
          details: null,
          request_id: session.headers.get('x-request-id')
        },
        { status: 502, headers: { 'Cache-Control': 'no-store' } }
      );
    }
    const user = await session.json();

    const cookieStore = await cookies();
    const secure = shouldUseSecureCookies(request);
    cookieStore.set(ACCESS_COOKIE, payload.access_token, {
      httpOnly: true,
      sameSite: 'lax',
      secure,
      path: '/',
      maxAge: 60 * 60
    });
    if (payload.refresh_token) {
      cookieStore.set('bidpilot_refresh_token', payload.refresh_token, {
        httpOnly: true,
        sameSite: 'lax',
        secure,
        path: '/',
        maxAge: 60 * 60 * 24 * 30
      });
    }
    return Response.json({ ok: true, user }, { headers: { 'Cache-Control': 'no-store' } });
  } catch {
    return unavailableResponse();
  }
}
