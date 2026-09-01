import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from '@/components/ui/accordion';
import { buttonVariants } from '@/components/ui/button';
import { BrandLogo } from '@/components/brand';
import { Icons } from '@/components/icons';
import { cn } from '@/lib/utils';
import { CenteredHero } from './CenteredHero';
import { CenteredMenu } from './CenteredMenu';
import { CTABanner } from './CTABanner';
import { FeatureCard } from './FeatureCard';
import { Section } from './Section';

/**
 * BidPilot composition of ixartz/SaaS-Boilerplate's marketing templates.
 * The upstream section order and responsive composition are retained while
 * product copy, routes and pricing claims are owned by BidPilot.
 */
export function SaasBoilerplateLanding() {
  return (
    <main className='min-h-svh bg-background' data-testid='saas-boilerplate-landing'>
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
                  创建工作区 <Icons.arrowRight data-icon='inline-end' />
                </Link>
              </li>
            </>
          }
        >
          <li>
            <Link href='#capabilities'>产品能力</Link>
          </li>
          <li>
            <Link href='#workflow'>响应工作流</Link>
          </li>
          <li>
            <Link href='#plans'>工作区权益</Link>
          </li>
          <li>
            <Link href='#faq'>常见问题</Link>
          </li>
        </CenteredMenu>
      </Section>

      <Section className='py-32 sm:py-36'>
        <CenteredHero
          banner={
            <Badge variant='outline' className='gap-1.5 px-3 py-1'>
              <Icons.sparkles data-icon='inline-start' />
              AI 招标响应工作台
            </Badge>
          }
          title={
            <>
              把招标资料变成
              <span className='text-primary underline decoration-primary/25 underline-offset-8'>
                有证据的响应方案
              </span>
            </>
          }
          description='从资料整理、要求识别到章节起草、评审和交付，BidPilot 为每个项目保留一条可追溯的响应链。'
          buttons={
            <>
              <Link className={buttonVariants({ size: 'lg' })} href='/auth/sign-up'>
                免费创建工作区 <Icons.arrowRight data-icon='inline-end' />
              </Link>
              <Link
                className={buttonVariants({ variant: 'outline', size: 'lg' })}
                href='/auth/sign-in'
              >
                进入现有工作区
              </Link>
            </>
          }
        />
        <div className='mx-auto mt-14 grid max-w-4xl gap-3 md:grid-cols-3'>
          <ProofItem
            icon={<Icons.workspace />}
            label='项目级资料隔离'
            detail='业务事实留在项目边界内'
          />
          <ProofItem
            icon={<Icons.badgeCheck />}
            label='证据可回溯'
            detail='结论连接来源和审核决定'
          />
          <ProofItem icon={<Icons.lock />} label='受控执行' detail='变更动作遵循权限和确认' />
        </div>
      </Section>

      <section className='border-y bg-secondary/55' id='workflow'>
        <Section
          subtitle='从资料到交付'
          title='一个项目，贯穿完整响应链。'
          description='从资料收集、要求核验到章节起草、评审和交付，每一步都围绕同一个项目工作区推进。'
        >
          <div className='grid grid-cols-2 gap-x-3 gap-y-6 md:grid-cols-6 md:gap-x-5'>
            {[
              ['资料包', <Icons.post key='source' />],
              ['要求', <Icons.forms key='requirements' />],
              ['证据', <Icons.badgeCheck key='evidence' />],
              ['章节', <Icons.product key='sections' />],
              ['评审', <Icons.teams key='review' />],
              ['交付', <Icons.fileTypeDoc key='delivery' />]
            ].map(([label, icon]) => (
              <div className='flex flex-col items-center gap-2 text-center' key={label as string}>
                <span className='text-primary [&_svg]:size-7'>{icon}</span>
                <span className='text-sm font-medium'>{label as string}</span>
              </div>
            ))}
          </div>
        </Section>
      </section>

      <section id='capabilities'>
        <Section
          subtitle='产品能力'
          title='让团队围绕同一份项目事实协作。'
          description='资料、要求、证据、章节和审核状态都可以回到项目工作区，不把关键决定埋在散落的聊天记录里。'
        >
          <div className='grid grid-cols-1 gap-x-3 gap-y-8 md:grid-cols-3'>
            <FeatureCard icon={<Icons.post />} title='资料与知识'>
              上传招标文件、企业材料和证据，建立项目可用的资料边界。
            </FeatureCard>
            <FeatureCard icon={<Icons.forms />} title='要求与证据'>
              将硬性要求拆成可检查条目，连接来源、引用和覆盖状态。
            </FeatureCard>
            <FeatureCard icon={<Icons.product />} title='章节与交付'>
              让每个章节拥有版本、证据和评审记录，交付前保持可核验。
            </FeatureCard>
            <FeatureCard icon={<Icons.sparkles />} title='Pi Agent 执行'>
              由执行助手根据项目事实推进任务，界面只呈现真实进度、工具和结果。
            </FeatureCard>
            <FeatureCard icon={<Icons.teams />} title='团队工作区'>
              成员、角色、项目权限和审核决定由 FastAPI 控制面统一校验。
            </FeatureCard>
            <FeatureCard icon={<Icons.lock />} title='安全边界'>
              Provider 密钥留在服务端，浏览器只拿到脱敏结果和可恢复的运行状态。
            </FeatureCard>
          </div>
        </Section>
      </section>

      <section className='border-y' id='plans'>
        <Section
          subtitle='工作区权益'
          title='从一个项目开始，再按团队需要扩展。'
          description='不同工作区提供不同的项目容量、协作和服务支持，具体权益以账户配置为准。'
        >
          <div className='grid grid-cols-1 gap-x-6 gap-y-8 @xl:grid-cols-3'>
            <PlanCard
              name='Starter'
              description='适合验证第一条投标响应链。'
              features={['3 个活跃项目', '基础资料与要求管理', '有限的官方 Agent 额度']}
            />
            <PlanCard
              name='Professional'
              description='适合持续推进投标的团队。'
              featured
              features={['更高项目与运行容量', '团队协作与评审工作区', '完整 Agent 与交付工作流']}
            />
            <PlanCard
              name='Enterprise'
              description='适合有治理和集成要求的组织。'
              features={['组织级权限治理', '定制化部署与支持', '按合同配置容量与服务']}
            />
          </div>
        </Section>
      </section>

      <section id='faq'>
        <Section
          subtitle='常见问题'
          title='开始使用前，先把边界讲清楚。'
          description='下面是使用 BidPilot 前最关键的产品边界。'
        >
          <Accordion multiple className='w-full'>
            <AccordionItem value='facts'>
              <AccordionTrigger>项目资料和业务事实由谁保存？</AccordionTrigger>
              <AccordionContent>
                业务事实以 FastAPI 控制面和 PostgreSQL 为准，Agent
                运行状态只是执行过程，不替代项目数据。
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value='agent'>
              <AccordionTrigger>Agent 的“正在思考”是真实状态吗？</AccordionTrigger>
              <AccordionContent>
                只有执行助手真实开始思考后才会显示对应状态，不用固定文案冒充进度。
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value='approval'>
              <AccordionTrigger>哪些动作需要人工确认？</AccordionTrigger>
              <AccordionContent>
                会改变项目、资料、审核或交付状态的动作由服务端策略判断，页面通过结构化确认控件呈现。
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value='keys'>
              <AccordionTrigger>我配置的模型 Key 会出现在浏览器吗？</AccordionTrigger>
              <AccordionContent>
                不会。Provider
                配置通过服务端保存和解密，浏览器只显示供应商和模型元数据，不回显密钥。
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value='start'>
              <AccordionTrigger>第一次体验应该从哪里开始？</AccordionTrigger>
              <AccordionContent>
                创建工作区后进入项目页，建立或打开一个投标项目，再上传资料包；之后可以从 Agent
                或项目工作区继续。
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </Section>
      </section>

      <Section>
        <CTABanner
          title='准备好让响应过程可追溯了吗？'
          description='先创建一个工作区，再用真实项目验证资料、证据和 Agent 执行链。'
          buttons={
            <Link
              className={cn(
                buttonVariants({ variant: 'secondary', size: 'lg' }),
                'whitespace-pre-line'
              )}
              href='/auth/sign-up'
            >
              开始创建工作区 <Icons.arrowRight data-icon='inline-end' />
            </Link>
          }
        />
      </Section>

      <footer className='border-t pb-16'>
        <Section className='pb-0'>
          <div className='flex flex-col items-center text-center'>
            <BrandLogo />
            <ul className='mt-4 flex gap-x-8 text-lg font-medium max-sm:flex-col [&_a:hover]:opacity-70'>
              <li>
                <Link href='#capabilities'>产品能力</Link>
              </li>
              <li>
                <Link href='#workflow'>响应工作流</Link>
              </li>
              <li>
                <Link href='#plans'>工作区权益</Link>
              </li>
              <li>
                <Link href='/auth/sign-in'>登录</Link>
              </li>
            </ul>
            <div className='text-muted-foreground mt-6 flex w-full items-center justify-between gap-y-2 border-t pt-3 text-sm max-md:flex-col'>
              <span>© {new Date().getFullYear()} BidPilot · DocPilot 招标响应工作台</span>
              <span className='inline-flex items-center gap-1.5'>
                <Icons.lock data-icon='inline-start' /> 服务端治理，用户可回看
              </span>
            </div>
          </div>
        </Section>
      </footer>
    </main>
  );
}

function ProofItem({
  icon,
  label,
  detail
}: {
  icon: React.ReactNode;
  label: string;
  detail: string;
}) {
  return (
    <div className='flex items-start gap-3 rounded-xl border bg-background px-4 py-4 text-left'>
      <span className='text-primary mt-0.5 [&_svg]:size-5'>{icon}</span>
      <span className='min-w-0'>
        <strong className='block text-sm font-semibold'>{label}</strong>
        <span className='text-muted-foreground mt-1 block text-xs leading-5'>{detail}</span>
      </span>
    </div>
  );
}

function PlanCard({
  name,
  description,
  features,
  featured = false
}: {
  name: string;
  description: string;
  features: string[];
  featured?: boolean;
}) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border px-6 py-8 text-center',
        featured && 'border-primary ring-1 ring-primary/20'
      )}
    >
      {featured && <Badge className='mb-3'>推荐团队起点</Badge>}
      <h3 className='text-lg font-semibold'>{name}</h3>
      <div className='mt-4 text-3xl font-bold'>按工作区</div>
      <div className='text-muted-foreground mt-1 text-sm'>权益以当前账户配置为准</div>
      <div className='mt-2 mb-5 text-sm text-muted-foreground'>{description}</div>
      <Link className={buttonVariants({ size: 'sm', className: 'w-full' })} href='/auth/sign-up'>
        创建工作区
      </Link>
      <ul className='mt-8 flex flex-col gap-3 text-left'>
        {features.map((feature) => (
          <li className='text-muted-foreground flex items-start gap-2 text-sm' key={feature}>
            <Icons.check className='text-primary mt-0.5 shrink-0' />
            <span>{feature}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
