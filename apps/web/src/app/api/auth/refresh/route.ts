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
    const refreshToken = (await cookies()).get('bidpilot_refresh_token')?.value;
    if (!refreshToken) {
      return Response.json(
        { code: 'unauthorized', message: '未登录。', detail: '未登录。' },
        { status: 401 }
      );
    }
    const upstream = await requestBackend(
      `/auth/refresh?refresh_token=${encodeURIComponent(refreshToken)}`,
      { method: 'POST', headers: { Accept: 'application/json' } },
      false
    );
    if (!upstream.ok) {
      const response = forwardBackendResponse(upstream);
      const cookieStore = await cookies();
      cookieStore.delete(ACCESS_COOKIE);
      cookieStore.delete('bidpilot_refresh_token');
      return response;
    }
    const payload = (await upstream.json()) as {
      access_token?: string;
      refresh_token?: string | null;
    };
    if (!payload.access_token)
      return Response.json({ message: '刷新响应缺少访问令牌。' }, { status: 502 });
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
    return Response.json({ ok: true });
  } catch {
    return unavailableResponse();
  }
}
