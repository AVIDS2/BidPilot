import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { OpenSaasLanding } from '@/components/marketing/open-saas/OpenSaasLanding';

export default async function Page() {
  if ((await cookies()).get('bidpilot_access_token')?.value) redirect('/dashboard');
  return <OpenSaasLanding />;
}
