import { forwardBackendResponse, requestBackend, unavailableResponse } from '@/lib/backend';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  try {
    const upstream = await requestBackend(
      '/auth/register',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: await request.text()
      },
      false
    );
    return forwardBackendResponse(upstream);
  } catch {
    return unavailableResponse();
  }
}
