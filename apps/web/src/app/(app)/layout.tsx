import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { AppShell } from '@/components/layout/app-shell';

export default async function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get('bidpilot_access_token')?.value;
  const refreshToken = cookieStore.get('bidpilot_refresh_token')?.value;
  const authRequired = process.env.DOCPILOT_AUTH_REQUIRED?.toLowerCase() === 'true';
  // The access token is intentionally short-lived. Keep the App Router tree
  // mounted when only the refresh cookie remains so /api/auth/me can renew the
  // session instead of turning an ordinary browser refresh into a logout.
  // Local development uses the API's documented dev fallback; production sets
  // authRequired=true and still redirects before rendering the workbench.
  if (authRequired && !accessToken && !refreshToken) redirect('/auth/sign-in');
  return <AppShell>{children}</AppShell>;
}
