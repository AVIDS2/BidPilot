import {
  renewSession,
  unavailableResponse
} from '@/lib/backend';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  try {
    const renewed = await renewSession(request);
    if (!renewed) {
      return Response.json(
        { code: 'unauthorized', message: '未登录。', detail: '未登录。' },
        { status: 401 }
      );
    }
    if ('response' in renewed) return renewed.response;
    return Response.json({ ok: true });
  } catch {
    return unavailableResponse();
  }
}
