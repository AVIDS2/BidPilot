import { ACCESS_COOKIE } from '@/lib/backend';
import { cookies } from 'next/headers';

export async function POST() {
  const cookieStore = await cookies();
  cookieStore.delete(ACCESS_COOKIE);
  cookieStore.delete('bidpilot_refresh_token');
  return Response.json({ ok: true });
}
