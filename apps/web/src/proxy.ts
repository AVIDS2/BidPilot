import { NextResponse, type NextRequest } from 'next/server';

export default function proxy(request: NextRequest) {
  return NextResponse.next({ request });
}

export const config = {
  matcher: ['/((?!_next|favicon.ico|.*\\..*).*)']
};
