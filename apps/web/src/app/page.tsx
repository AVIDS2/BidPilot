import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { SaasBoilerplateLanding } from '@/components/marketing/saas-boilerplate/SaasBoilerplateLanding';

export default async function Page() {
  if ((await cookies()).get('bidpilot_access_token')?.value) redirect('/dashboard');
  return <SaasBoilerplateLanding />;
}
