import { AuthForm } from '@/components/auth/auth-form';

export const metadata = { title: '登录' };

export default function SignInPage() {
  return <AuthForm mode='sign-in' />;
}
