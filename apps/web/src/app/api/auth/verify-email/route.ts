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
    const token = new URL(request.url).searchParams.get('token');
    if (!token)
      return Response.json(
        { code: 'validation_error', message: '验证链接缺少 token。' },
        { status: 400 }
      );
    const upstream = await requestBackend(
      `/auth/verify-email?token=${encodeURIComponent(token)}`,
      { method: 'POST', headers: { Accept: 'application/json' } },
      false
    );
    if (!upstream.ok) return forwardBackendResponse(upstream);
    const payload = (await upstream.json()) as {
      access_token?: string;
      refresh_token?: string | null;
      message?: string;
    };
    if (!payload.access_token)
      return Response.json(
        { message: payload.message || '验证响应缺少访问令牌。' },
        { status: 502 }
      );
    const cookieStore = await cookies();
    const secure = shouldUseSecureCookies(request);
    cookieStore.set(ACCESS_COOKIE, payload.access_token, {
      httpOnly: true,
      sameSite: 'lax',
      secure,
      path: '/',
      maxAge: 60 * 60
    });
    if (payload.refresh_token)
      cookieStore.set('bidpilot_refresh_token', payload.refresh_token, {
        httpOnly: true,
        sameSite: 'lax',
        secure,
        path: '/',
        maxAge: 60 * 60 * 24 * 30
      });
    return Response.json({ ok: true, message: payload.message || '邮箱验证成功。' });
  } catch {
    return unavailableResponse();
  }
}
