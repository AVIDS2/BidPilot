import {
  forwardBackendResponse,
  requestBackend,
  renewSession,
  unavailableResponse,
  ACCESS_COOKIE
} from '@/lib/backend';
import { cookies } from 'next/headers';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  try {
    const cookieStore = await cookies();
    let accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
    let upstream = accessToken
      ? await requestBackend(
          '/auth/me',
          { headers: { Accept: 'application/json', Authorization: `Bearer ${accessToken}` } },
          false
        )
      : null;

    // A missing or expired access token is an expected refresh boundary, not
    // an unauthenticated browser. Only a definitive refresh rejection clears
    // the session; 429/5xx responses are returned unchanged for retry.
    if (!upstream || upstream.status === 401) {
      const renewed = await renewSession(request);
      if (!renewed) {
        return Response.json(
          { code: 'unauthorized', message: '未登录。', detail: '未登录。', request_id: null },
          { status: 401, headers: { 'Cache-Control': 'no-store' } }
        );
      }
      if ('response' in renewed) return renewed.response;
      accessToken = renewed.accessToken;
      upstream = await requestBackend(
        '/auth/me',
        { headers: { Accept: 'application/json', Authorization: `Bearer ${accessToken}` } },
        false
      );
    }

    if (!upstream) {
      return Response.json(
        { code: 'unauthorized', message: '未登录。', detail: '未登录。', request_id: null },
        { status: 401, headers: { 'Cache-Control': 'no-store' } }
      );
    }
    return forwardBackendResponse(upstream);
  } catch {
    return unavailableResponse();
  }
}
