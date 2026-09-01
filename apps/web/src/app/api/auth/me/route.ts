import {
  forwardBackendResponse,
  requestBackend,
  unavailableResponse,
  ACCESS_COOKIE
} from '@/lib/backend';
import { cookies } from 'next/headers';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    if (!(await cookies()).get(ACCESS_COOKIE)?.value) {
      return Response.json(
        { code: 'unauthorized', message: '未登录。', detail: '未登录。', request_id: null },
        { status: 401, headers: { 'Cache-Control': 'no-store' } }
      );
    }
    const upstream = await requestBackend('/auth/me', { headers: { Accept: 'application/json' } });
    return forwardBackendResponse(upstream);
  } catch {
    return unavailableResponse();
  }
}
