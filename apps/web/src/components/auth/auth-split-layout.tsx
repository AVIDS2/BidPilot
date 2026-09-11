import Link from 'next/link';
import { buttonVariants } from '@/components/ui/button';
import { BrandLogo } from '@/components/brand';
import { cn } from '@/lib/utils';
import { InteractiveGridPattern } from './interactive-grid';

/**
 * Adapted from the first-party seat-reserver Kiranism auth shell. The
 * split-screen composition, responsive behavior and interactive grid are
 * preserved; BidPilot owns the copy and authentication form.
 */
export function AuthSplitLayout({
  mode,
  children
}: {
  mode: 'sign-in' | 'sign-up';
  children: React.ReactNode;
}) {
  const isSignIn = mode === 'sign-in';
  return (
    <main className='bg-muted/20 grid min-h-[100dvh] lg:grid-cols-[0.9fr_1.1fr]'>
      <section className='bg-foreground text-background relative hidden overflow-hidden p-10 lg:flex lg:flex-col'>
        <div className='relative z-10 flex items-center gap-2 text-sm font-semibold'>
          <BrandLogo textClassName='text-background' />
        </div>
        <InteractiveGridPattern
          className={cn(
            'mask-[radial-gradient(400px_circle_at_center,white,transparent)]',
            'inset-x-0 inset-y-[0%] h-full skew-y-12'
          )}
        />
        <div className='relative z-10 mt-auto max-w-md'>
          <p className='text-background/60 mb-4 text-xs font-medium tracking-[0.18em] uppercase'>
            {isSignIn ? 'Evidence-led bid operations' : 'A clearer way to respond'}
          </p>
          <h1 className='text-4xl leading-tight font-semibold tracking-tight'>
            {isSignIn ? '把每一次响应，交给更稳定的工作流。' : '让招标资料，进入一套清晰的工作台。'}
          </h1>
          <p className='text-background/65 mt-5 text-sm leading-6'>
            {isSignIn
              ? '统一管理项目、证据和助手工作结果，让团队始终围绕同一份业务事实协作。'
              : '从资料、要求到证据和交付，每一个决定都可以被看见、核对和回溯。'}
          </p>
        </div>
      </section>

      <section className='flex items-center justify-center px-6 py-12'>
        <div className='w-full max-w-md'>
          <div className='mb-10 flex items-center justify-between'>
            <Link href='/' className='lg:hidden' aria-label='BidPilot 首页'>
              <BrandLogo />
            </Link>
            <Link
              href={isSignIn ? '/auth/sign-up' : '/auth/sign-in'}
              className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'ml-auto')}
            >
              {isSignIn ? '创建工作区' : '已有账号'}
            </Link>
          </div>
          <div className='mb-8'>
            <p className='text-muted-foreground mb-3 text-sm'>
              {isSignIn ? '欢迎回来' : '开始使用'}
            </p>
            <h2 className='text-3xl font-semibold tracking-tight'>
              {isSignIn ? '进入 BidPilot 工作台' : '创建你的工作区'}
            </h2>
            <p className='text-muted-foreground mt-2 text-sm leading-6'>
              {isSignIn
                ? '使用邮箱进入你的项目、知识库和 Copilot 工作进展。'
                : '用一个真实工作区开始管理招标资料和响应任务。'}
            </p>
          </div>
          {children}
        </div>
      </section>
    </main>
  );
}
