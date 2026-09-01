import { requestBackend, unavailableResponse } from '@/lib/backend';

export const dynamic = 'force-dynamic';

type RouteContext = { params: Promise<{ path: string[] }> };

async function forward(request: Request, context: RouteContext) {
  try {
    const { path } = await context.params;
    const url = new URL(request.url);
    const backendPath = `/${path.map((segment) => encodeURIComponent(segment)).join('/')}${url.search}`;
    const headers = new Headers();
    const accept = request.headers.get('accept');
    const contentType = request.headers.get('content-type');
    if (accept) headers.set('Accept', accept);
    if (contentType) headers.set('Content-Type', contentType);
    const body =
      request.method === 'GET' || request.method === 'HEAD'
        ? undefined
        : await request.arrayBuffer();
    const upstream = await requestBackend(backendPath, { method: request.method, headers, body });
    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.set('Cache-Control', 'no-store');
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders
    });
  } catch {
    return unavailableResponse();
  }
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
