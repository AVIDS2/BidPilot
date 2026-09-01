import Link from 'next/link';
import { ArrowRight, Check } from 'lucide-react';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from '@/components/ui/accordion';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import { BrandLogo } from '@/components/brand';
import { Icons } from '@/components/icons';
import { CenteredMenu } from '@/components/marketing/saas-boilerplate/CenteredMenu';
import { Section } from '@/components/marketing/saas-boilerplate/Section';
import { ThemeModeToggle } from '@/components/themes/theme-mode-toggle';
import { ThemeSelector } from '@/components/themes/theme-selector';
import { cn } from '@/lib/utils';

const plans = [
  {
    name: 'Starter',
    description: '适合验证第一条投标响应链。',
    features: ['3 个活跃项目', '资料、要求和证据基础能力', '官方 Agent 体验额度']
  },
  {
    name: 'Professional',
    description: '适合持续推进投标的响应团队。',
    featured: true,
    features: ['更高项目与运行容量', '团队协作和评审工作区', '完整 Agent 与交付工作流']
  },
  {
    name: 'Enterprise',
    description: '适合有治理、集成和部署要求的组织。',
    features: ['组织级权限治理', '定制化部署与支持', '按合同配置容量和服务']
  }
];

export const metadata = {
  title: '工作区权益',
  description: 'BidPilot 工作区权益和团队能力。'
};

export default function PricingPage() {
  return (
    <main className='min-h-svh bg-background'>
      <Section className='px-3 py-6'>
        <CenteredMenu
          logo={<BrandLogo />}
          rightMenu={
            <>
              <li>
                <ThemeModeToggle />
              </li>
              <li className='hidden sm:block'>
                <ThemeSelector />
              </li>
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
        subtitle='工作区权益'
        title='按团队需要扩展响应能力。'
        description='先从一个真实项目开始，随着团队协作和交付规模增长再扩展工作区能力。'
      >
        <div className='grid gap-5 md:grid-cols-3'>
          {plans.map((plan) => (
            <Card
              className={cn(
                'relative flex h-full flex-col',
                plan.featured && 'border-primary ring-1 ring-primary/20'
              )}
              key={plan.name}
            >
              {plan.featured && <Badge className='absolute top-4 right-4'>推荐团队起点</Badge>}
              <CardHeader>
                <CardTitle>{plan.name}</CardTitle>
                <CardDescription>{plan.description}</CardDescription>
              </CardHeader>
              <CardContent className='flex-1'>
                <p className='text-2xl font-semibold'>按工作区配置</p>
                <p className='text-muted-foreground mt-1 text-sm'>
                  正式商业价格以账户配置和合同为准。
                </p>
                <ul className='mt-6 flex flex-col gap-3'>
                  {plan.features.map((feature) => (
                    <li
                      className='text-muted-foreground flex items-start gap-2 text-sm'
                      key={feature}
                    >
                      <Check className='text-primary mt-0.5' />
                      {feature}
                    </li>
                  ))}
                </ul>
              </CardContent>
              <CardFooter>
                <Link className={buttonVariants({ className: 'w-full' })} href='/auth/sign-up'>
                  创建工作区 <ArrowRight data-icon='inline-end' />
                </Link>
              </CardFooter>
            </Card>
          ))}
        </div>
      </Section>
      <Section subtitle='常见问题' title='先把商业边界讲清楚。'>
        <Accordion multiple>
          <AccordionItem value='price'>
            <AccordionTrigger>页面为什么不直接展示固定金额？</AccordionTrigger>
            <AccordionContent>
              当前工作区额度、官方模型使用和企业定制能力由服务端账户配置决定，营销页不会虚构一个无法兑现的价格。
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value='upgrade'>
            <AccordionTrigger>后续如何升级工作区？</AccordionTrigger>
            <AccordionContent>
              登录后从账户和管理员工作区查看当前计划、额度和计费入口，支付状态会自动同步。
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value='data'>
            <AccordionTrigger>升级会影响项目资料吗？</AccordionTrigger>
            <AccordionContent>
              不会。项目、资料、证据和审核记录由 BidPilot 控制面保存，计划只决定可用额度和组织能力。
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </Section>
      <footer className='border-t pb-16'>
        <Section className='pb-0'>
          <div className='flex flex-col items-center gap-4 text-center'>
            <BrandLogo />
            <p className='text-muted-foreground text-sm'>
              © {new Date().getFullYear()} BidPilot · DocPilot 招标响应工作台
            </p>
            <Link className={buttonVariants({ variant: 'ghost', size: 'sm' })} href='/'>
              返回首页 <Icons.arrowRight data-icon='inline-end' />
            </Link>
          </div>
        </Section>
      </footer>
    </main>
  );
}
