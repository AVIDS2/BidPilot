import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { AppShell } from '@/components/layout/app-shell';

export default async function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get('bidpilot_access_token')?.value;
  const refreshToken = cookieStore.get('bidpilot_refresh_token')?.value;
  // The access token is intentionally short-lived. Keep the App Router tree
  // mounted when only the refresh cookie remains so /api/auth/me can renew the
  // session instead of turning an ordinary browser refresh into a logout.
  if (!accessToken && !refreshToken) redirect('/auth/sign-in');
  return <AppShell>{children}</AppShell>;
}
