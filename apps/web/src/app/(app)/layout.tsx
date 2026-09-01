import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { AppShell } from '@/components/layout/app-shell';

export default async function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  const token = (await cookies()).get('bidpilot_access_token')?.value;
  if (!token) redirect('/auth/sign-in');
  return <AppShell>{children}</AppShell>;
}
