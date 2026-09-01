import Link from 'next/link';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import {
  ArrowRight,
  Check,
  FileCheck2,
  Files,
  FolderKanban,
  Sparkles,
  Workflow
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BrandLogo } from '@/components/brand';
import { IxartzHero, IxartzSection } from '@/components/marketing/ixartz-landing';

export default async function Page() {
  const hasSession = Boolean((await cookies()).get('bidpilot_access_token')?.value);
  if (hasSession) redirect('/dashboard');

  return (
    <main className='min-h-svh bg-background'>
      <header className='border-b'>
        <div className='mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-5 lg:px-8'>
          <Link href='/' aria-label='BidPilot 首页'>
            <BrandLogo />
          </Link>
          <nav
            className='hidden items-center gap-6 text-sm text-muted-foreground md:flex'
            aria-label='主导航'
          >
            <Link className='transition-colors hover:text-foreground' href='#workflow'>
              工作流
            </Link>
            <Link className='transition-colors hover:text-foreground' href='#evidence'>
              证据链
            </Link>
            <Link className='transition-colors hover:text-foreground' href='#security'>
              安全与权限
            </Link>
          </nav>
          <div className='flex items-center gap-2'>
            <Link className={buttonVariants({ variant: 'ghost' })} href='/auth/sign-in'>
              登录
            </Link>
            <Link className={buttonVariants()} href='/auth/sign-up'>
              创建工作区 <ArrowRight data-icon='inline-end' />
            </Link>
          </div>
        </div>
      </header>

      <section className='border-b'>
        <div className='mx-auto grid max-w-7xl gap-12 px-5 py-20 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:px-8 lg:py-28'>
          <div className='max-w-2xl'>
            <Badge variant='outline' className='mb-6 gap-1.5 px-2.5 py-1'>
              <Sparkles className='size-3.5' />
              AI 招标响应工作台
            </Badge>
            <IxartzHero
              title='把招标资料，变成有证据的响应方案。'
              description='从项目资料、需求拆解到章节起草、评审和交付，BidPilot 把每一步都保留在可追溯的项目工作区里。'
              actions={
                <>
                  <Link className={buttonVariants({ size: 'lg' })} href='/auth/sign-up'>
                    免费创建工作区 <ArrowRight data-icon='inline-end' />
                  </Link>
                  <Link
                    className={buttonVariants({ size: 'lg', variant: 'outline' })}
                    href='/auth/sign-in'
                  >
                    进入现有工作区
                  </Link>
                </>
              }
            >
              <div className='text-muted-foreground mt-8 flex flex-wrap gap-x-5 gap-y-2 text-sm'>
                {['项目级资料隔离', '每条结论可回溯', '人工确认后再交付'].map((item) => (
                  <span className='inline-flex items-center gap-1.5' key={item}>
                    <Check className='text-primary size-4' />
                    {item}
                  </span>
                ))}
              </div>
            </IxartzHero>
          </div>
          <div className='relative'>
            <div className='bg-card overflow-hidden rounded-xl border shadow-sm'>
              <div className='flex items-center justify-between border-b px-5 py-4'>
                <div className='flex items-center gap-2'>
                  <FolderKanban className='text-primary size-4' />
                  <span className='text-sm font-medium'>项目完整度检查</span>
                </div>
                <Badge variant='secondary'>运行中</Badge>
              </div>
              <div className='grid gap-3 p-5'>
                {[
                  ['读取项目资料', '已完成', 'text-emerald-600'],
                  ['解析资格与商务要求', '已完成', 'text-emerald-600'],
                  ['匹配可引用证据', '进行中', 'text-primary'],
                  ['生成响应章节', '等待中', 'text-muted-foreground']
                ].map(([label, status, tone]) => (
                  <div className='flex items-center gap-3 rounded-lg border px-3 py-3' key={label}>
                    <Workflow className={`size-4 ${tone}`} />
                    <span className='min-w-0 flex-1 truncate text-sm'>{label}</span>
                    <span className={`text-xs ${tone}`}>{status}</span>
                  </div>
                ))}
                <div className='bg-muted/50 mt-2 rounded-lg p-4'>
                  <p className='text-muted-foreground text-xs'>当前任务</p>
                  <p className='mt-1 text-sm leading-6'>
                    检查资料完整度，确认需求、证据和就绪缺口。
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <IxartzSection id='workflow' className='py-20'>
        <div className='max-w-2xl'>
          <p className='text-primary text-sm font-medium'>为真实投标流程设计</p>
          <h2 className='mt-3 text-3xl font-semibold tracking-tight'>一个项目，贯穿完整响应链。</h2>
          <p className='text-muted-foreground mt-4 leading-7'>
            资料和业务事实留在项目里，Agent 只负责执行经过授权的动作，并把过程实时呈现出来。
          </p>
        </div>
        <div className='mt-10 grid gap-4 md:grid-cols-3'>
          <FeatureCard
            icon={<Files />}
            title='资料与知识'
            copy='上传招标文件、企业材料和证据，形成项目可用的资料边界。'
          />
          <FeatureCard
            icon={<FileCheck2 />}
            title='要求与证据'
            copy='把硬性要求拆成可检查条目，连接来源、引用和覆盖状态。'
          />
          <FeatureCard
            icon={<Workflow />}
            title='Agent 与交付'
            copy='实时查看 Pi 工具执行、思考边界、人工确认和最终交付物。'
          />
        </div>
      </IxartzSection>

      <section id='evidence' className='border-y bg-muted/25'>
        <div className='mx-auto grid max-w-7xl gap-12 px-5 py-20 lg:grid-cols-2 lg:px-8'>
          <div>
            <h2 className='text-3xl font-semibold tracking-tight'>
              不是一段生成文本，而是一条证据链。
            </h2>
            <p className='text-muted-foreground mt-4 max-w-xl leading-7'>
              每个章节都可以回到需求、来源文件和审核决定。团队成员看到的是同一份项目事实，而不是散落在聊天记录里的结论。
            </p>
          </div>
          <div className='grid gap-3'>
            {['来源文件', '需求条目', '证据引用', '章节版本', '审核决定'].map((item, index) => (
              <div
                className='flex items-center gap-3 rounded-lg border bg-background px-4 py-3'
                key={item}
              >
                <span className='bg-primary/10 text-primary flex size-7 items-center justify-center rounded-md text-xs font-semibold'>
                  {index + 1}
                </span>
                <span className='text-sm'>{item}</span>
                <ArrowRight className='text-muted-foreground ml-auto size-4' />
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id='security' className='mx-auto max-w-7xl px-5 py-20 lg:px-8'>
        <Card className='bg-foreground text-background border-0'>
          <CardHeader>
            <CardTitle className='text-background text-2xl'>
              从第一个项目开始，保持业务事实可控。
            </CardTitle>
          </CardHeader>
          <CardContent className='flex flex-col justify-between gap-6 sm:flex-row sm:items-end'>
            <p className='text-background/70 max-w-xl leading-7'>
              工作区、项目和成员权限由 FastAPI 控制面统一校验，Agent 运行事件和交付版本可随时回看。
            </p>
            <Link className={buttonVariants({ variant: 'secondary' })} href='/auth/sign-up'>
              创建工作区 <ArrowRight data-icon='inline-end' />
            </Link>
          </CardContent>
        </Card>
      </section>
      <footer className='border-t'>
        <div className='text-muted-foreground mx-auto flex max-w-7xl flex-col gap-3 px-5 py-8 text-sm sm:flex-row sm:items-center sm:justify-between lg:px-8'>
          <BrandLogo textClassName='text-foreground' />
          <span>BidPilot · DocPilot 招标响应工作台</span>
        </div>
      </footer>
    </main>
  );
}

function FeatureCard({
  icon,
  title,
  copy
}: {
  icon: React.ReactNode;
  title: string;
  copy: string;
}) {
  return (
    <Card>
      <CardHeader>
        <div className='bg-primary/10 text-primary mb-2 flex size-9 items-center justify-center rounded-lg [&_svg]:size-4'>
          {icon}
        </div>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className='text-muted-foreground leading-6'>{copy}</p>
      </CardContent>
    </Card>
  );
}
