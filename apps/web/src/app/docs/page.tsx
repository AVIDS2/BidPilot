import Link from 'next/link';
import { ArrowRight, BookOpen, FileCheck2, ShieldCheck, Sparkles } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { BrandLogo } from '@/components/brand';
import { CenteredMenu } from '@/components/marketing/saas-boilerplate/CenteredMenu';
import { Section } from '@/components/marketing/saas-boilerplate/Section';

export const metadata = {
  title: '产品说明',
  description: 'BidPilot 从资料到响应交付的产品说明。'
};

const sections = [
  {
    icon: BookOpen,
    title: '1. 建立项目资料边界',
    description:
      '每个投标项目拥有独立的资料包、企业材料、需求和交付物。先上传资料，再从项目页查看解析状态。'
  },
  {
    icon: FileCheck2,
    title: '2. 形成要求与证据链',
    description:
      '要求清单记录来源定位、重要程度、覆盖状态和核验结果；业务事实以服务端项目数据为准。'
  },
  {
    icon: Sparkles,
    title: '3. 让 Pi Agent 执行工作',
    description:
      'Agent 通过 Pi 原生事件和服务端业务工具推进任务，页面只呈现真实的思考、工具、审批和终态事件。'
  },
  {
    icon: ShieldCheck,
    title: '4. 评审后再交付',
    description:
      '章节、证据、评审线程和导出状态保留在同一条项目链路中，管理员权限和用户工作流分开校验。'
  }
];

export default function DocsPage() {
  return (
    <main className='min-h-svh bg-background'>
      <Section className='px-3 py-6'>
        <CenteredMenu
          logo={<BrandLogo />}
          rightMenu={
            <>
              <li>
                <Link href='/auth/sign-in'>登录</Link>
              </li>
              <li>
                <Link className={buttonVariants()} href='/auth/sign-up'>
                  创建工作区 <ArrowRight data-icon='inline-end' />
                </Link>
              </li>
            </>
          }
        >
          <li>
            <Link href='/'>产品能力</Link>
          </li>
          <li>
            <Link href='/docs'>产品说明</Link>
          </li>
          <li>
            <Link href='/pricing'>工作区权益</Link>
          </li>
        </CenteredMenu>
      </Section>
      <Section
        subtitle='产品说明'
        title='从资料到可交付响应的一条工作路径。'
        description='这份说明只描述当前 BidPilot 已实现的用户工作流，不把模板默认能力或开发者内部诊断包装成产品功能。'
      >
        <div className='grid gap-4 md:grid-cols-2'>
          {sections.map(({ icon: Icon, title, description }) => (
            <Card key={title}>
              <CardHeader>
                <div className='bg-primary/10 text-primary flex size-9 items-center justify-center rounded-lg'>
                  <Icon />
                </div>
                <CardTitle className='mt-2'>{title}</CardTitle>
                <CardDescription className='leading-6'>{description}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </Section>
      <Section subtitle='实际入口' title='按工作目标进入页面。'>
        <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-4'>
          {[
            ['项目', '/projects', '建立资料和响应工作区'],
            ['招采雷达', '/radar', '研判公开机会并转换项目'],
            ['我的工作', '/my-work', '处理缺口和待审批事项'],
            ['Agent', '/agent', '发起受控的项目任务']
          ].map(([label, href, detail]) => (
            <Link
              className='group rounded-xl border p-4 transition-colors hover:bg-muted/40'
              href={href}
              key={href}
            >
              <Badge variant='outline'>{label}</Badge>
              <p className='mt-3 text-sm font-medium'>{detail}</p>
              <span className='text-muted-foreground mt-4 inline-flex items-center gap-1 text-xs group-hover:text-foreground'>
                打开入口 <ArrowRight />
              </span>
            </Link>
          ))}
        </div>
      </Section>
      <footer className='border-t pb-16'>
        <Section className='pb-0'>
          <div className='flex flex-col items-center gap-4 text-center'>
            <BrandLogo />
            <p className='text-muted-foreground text-sm'>需要从真实项目开始？</p>
            <Link className={buttonVariants({ size: 'lg' })} href='/auth/sign-up'>
              创建工作区 <ArrowRight data-icon='inline-end' />
            </Link>
          </div>
        </Section>
      </footer>
    </main>
  );
}
