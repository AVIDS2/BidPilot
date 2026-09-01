import { requestBackend, ACCESS_COOKIE, unavailableResponse } from '@/lib/backend';
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
    if (!upstream.ok)
      return new Response(upstream.body, { status: upstream.status, headers: upstream.headers });

    const payload = (await upstream.json()) as {
      access_token?: string;
      refresh_token?: string | null;
    };
    if (!payload.access_token)
      return Response.json({ message: '登录响应缺少访问令牌。' }, { status: 502 });

    const cookieStore = await cookies();
    const secure = process.env.NODE_ENV === 'production';
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
    return Response.json({ ok: true });
  } catch {
    return unavailableResponse();
  }
}
