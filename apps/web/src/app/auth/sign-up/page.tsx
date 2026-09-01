import { AuthForm } from '@/components/auth/auth-form';

export const metadata = { title: '创建账户' };

export default function SignUpPage() {
  return <AuthForm mode='sign-up' />;
}
