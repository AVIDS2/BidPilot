'use client';

import * as React from 'react';
import Link from 'next/link';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from '@/components/ui/accordion';
import { Button, buttonVariants } from '@/components/ui/button';
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
import { ThemeModeToggle } from '@/components/themes/theme-mode-toggle';
import { ThemeSelector } from '@/components/themes/theme-selector';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger
} from '@/components/ui/sheet';
import { cn } from '@/lib/utils';

const navigationItems = [
  { name: '产品', href: '#features' },
  { name: '怎么工作', href: '#workflow' },
  { name: '适合谁', href: '#teams' },
  { name: '定价', href: '/pricing' },
  { name: '常见问题', href: '#faq' }
];

const examples = [
  {
    name: '项目响应工作区',
    description: '从机会到方案，始终知道下一步。',
    href: '/projects',
    surface: 'workspace' as const
  },
  {
    name: 'AI 助手',
    description: '找到重点，补齐证据，快速起草。',
    href: '/agent',
    surface: 'agent' as const
  },
  {
    name: '招标雷达',
    description: '不错过值得跟进的每个机会。',
    href: '/radar',
    surface: 'radar' as const
  },
  {
    name: '证据与审核',
    description: '让每个判断，都更快获得确认。',
    href: '/reviews',
    surface: 'review' as const
  }
];

const featureItems = [
  {
    name: '证据链',
    description: '每个关键判断，都能追溯来源。',
    icon: Icons.badgeCheck,
    size: 'small' as const,
    href: '/requirements'
  },
  {
    name: '招标雷达',
    description: '不错过值得跟进的每个机会。',
    icon: Icons.radar,
    size: 'small' as const,
    href: '/radar'
  },
  {
    name: '项目工作区',
    description: '所有资料，围绕一个项目展开。',
    size: 'medium' as const,
    icon: Icons.workspace,
    href: '/projects'
  },
  {
    name: '章节起草',
    description: '把要求，变成能直接使用的内容。',
    icon: Icons.edit,
    size: 'large' as const,
    href: '/agent'
  },
  {
    name: '缺口检查',
    description: '提前发现遗漏，减少最后返工。',
    icon: Icons.forms,
    size: 'large' as const,
    href: '/requirements'
  },
  {
    name: '可追溯交付',
    description: '版本清晰，交付更安心。',
    icon: Icons.fileTypeDoc,
    size: 'small' as const,
    href: '/deliverables'
  },
  {
    name: '团队审核',
    description: '让意见快速汇聚，决定及时落地。',
    icon: Icons.teams,
    size: 'small' as const,
    href: '/members'
  },
  {
    name: '版本对比',
    description: '看清每次修改，保留正确判断。',
    icon: Icons.checks,
    size: 'medium' as const,
    href: '/deliverables'
  },
  {
    name: '交付导出',
    description: '整理成一版，直接交给团队。',
    icon: Icons.externalLink,
    size: 'medium' as const,
    href: '/deliverables'
  }
];

const roleSurfaces = [
  {
    role: '投标负责人',
    title: '一眼掌握全局',
    detail: '进度、材料和风险清楚可见。',
    href: '/projects'
  },
  {
    role: '方案工程师',
    title: '直接从重点开始',
    detail: '从要求和证据出发，少做重复工作。',
    href: '/agent'
  },
  {
    role: '审核负责人',
    title: '快速确认关键事项',
    detail: '集中处理缺口、版本和待确认内容。',
    href: '/reviews'
  }
];

export function OpenSaasLanding() {
  return (
    <div className='bg-background text-foreground' data-testid='open-saas-landing'>
      <main className='isolate'>
        <OpenSaasNavBar />
        <OpenSaasHero />
        <ExamplesCarousel />
        <HighlightedFeature />
        <FeaturesGrid />
        <UseCases />
        <Faq />
      </main>
      <OpenSaasFooter />
    </div>
  );
}

function OpenSaasNavBar() {
  const [isScrolled, setIsScrolled] = React.useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);

  React.useEffect(() => {
    let frame: number | null = null;
    const update = () => {
      frame = null;
      setIsScrolled(window.scrollY > 0);
    };
    const handleScroll = () => {
      if (frame === null) frame = window.requestAnimationFrame(update);
    };
    update();
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', handleScroll);
      if (frame !== null) window.cancelAnimationFrame(frame);
    };
  }, []);

  const closeMenu = () => setMobileMenuOpen(false);

  return (
    <header className={cn('sticky top-0 z-50 transition-all duration-300', isScrolled && 'pt-4')}>
      <div
        className={cn(
          'transition-all duration-300',
          isScrolled
            ? 'border-border bg-background/95 mx-4 rounded-full border pr-2 shadow-lg backdrop-blur-lg md:mx-20 lg:pr-0'
            : 'border-border bg-background/85 border-b backdrop-blur-lg'
        )}
      >
        <nav
          className={cn(
            'mx-auto flex max-w-7xl items-center justify-between gap-4 transition-all duration-300',
            isScrolled ? 'p-3 lg:px-6' : 'p-5 lg:px-8'
          )}
          aria-label='主导航'
        >
          <Link href='/' className='text-foreground hover:text-primary flex shrink-0 items-center'>
            <BrandLogo markClassName={isScrolled ? 'size-7' : 'size-8'} />
          </Link>
          <ul className='ml-4 hidden items-center gap-6 lg:flex'>
            {navigationItems.map((item) => (
              <li key={item.href}>
                <a
                  href={item.href}
                  className={cn(
                    'text-muted-foreground hover:text-foreground text-sm transition-colors duration-300',
                    isScrolled && 'text-xs'
                  )}
                >
                  {item.name}
                </a>
              </li>
            ))}
          </ul>
          <div className='ml-auto flex items-center justify-end gap-2'>
            <div className='hidden xl:block'>
              <ThemeSelector />
            </div>
            <ThemeModeToggle />
            <Link
              href='/auth/sign-in'
              className={cn(
                'text-muted-foreground hover:text-foreground hidden text-sm transition-colors sm:block',
                isScrolled && 'text-xs'
              )}
            >
              登录
            </Link>
            <Link
              href='/auth/sign-up'
              className={cn(
                buttonVariants({ size: isScrolled ? 'sm' : 'default' }),
                'hidden sm:inline-flex'
              )}
            >
              开始一次响应 <Icons.arrowRight data-icon='inline-end' />
            </Link>
            <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
              <SheetTrigger
                render={
                  <Button variant='ghost' size='icon-sm' aria-label='打开导航'>
                    <Icons.menu />
                  </Button>
                }
              />
              <SheetContent side='right' className='w-[min(88vw,24rem)]'>
                <SheetHeader className='border-border border-b text-left'>
                  <SheetTitle>
                    <BrandLogo />
                  </SheetTitle>
                  <SheetDescription>让投标响应更有把握</SheetDescription>
                </SheetHeader>
                <nav className='flex flex-col gap-1 px-4' aria-label='移动端主导航'>
                  {navigationItems.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={closeMenu}
                      className={cn(
                        buttonVariants({ variant: 'ghost', size: 'lg' }),
                        'justify-start'
                      )}
                    >
                      {item.name}
                    </Link>
                  ))}
                  <Link
                    href='/auth/sign-in'
                    onClick={closeMenu}
                    className={cn(
                      buttonVariants({ variant: 'ghost', size: 'lg' }),
                      'justify-start'
                    )}
                  >
                    登录
                  </Link>
                  <Link
                    href='/auth/sign-up'
                    onClick={closeMenu}
                    className={cn(buttonVariants({ size: 'lg' }), 'mt-2 w-full')}
                  >
                    开始一次响应 <Icons.arrowRight data-icon='inline-end' />
                  </Link>
                  <div className='border-border mt-4 border-t pt-4'>
                    <ThemeSelector />
                  </div>
                </nav>
              </SheetContent>
            </Sheet>
          </div>
        </nav>
      </div>
    </header>
  );
}

function OpenSaasHero() {
  return (
    <section className='relative w-full pt-14'>
      <div
        className='bg-primary/5 pointer-events-none absolute inset-x-0 top-0 -z-10 h-96 blur-3xl'
        aria-hidden='true'
      />
      <div className='mx-auto max-w-7xl px-5 lg:px-8'>
        <div className='mx-auto max-w-3xl text-center md:py-20'>
          <p className='text-primary mb-5 font-mono text-xs tracking-[0.18em] uppercase'>
            让好机会，更快变成好方案
          </p>
          <h1 className='text-foreground text-5xl leading-tight font-bold sm:text-6xl'>
            把每一次投标响应，
            <br />
            <span className='text-primary'>做得更快、更稳</span>
          </h1>
          <p className='text-muted-foreground mx-auto mt-6 max-w-2xl text-lg leading-8'>
            从发现机会到交付方案，始终围绕同一份事实推进。
          </p>
          <div className='mt-10 flex flex-wrap items-center justify-center gap-3'>
            <Link className={buttonVariants({ variant: 'outline', size: 'lg' })} href='#workflow'>
              了解产品 <Icons.chevronDown data-icon='inline-end' />
            </Link>
            <Link className={buttonVariants({ size: 'lg' })} href='/auth/sign-up'>
              开始一次响应 <Icons.arrowRight data-icon='inline-end' />
            </Link>
          </div>
        </div>
        <div className='flow-root sm:mt-4'>
          <ProjectShowcase />
        </div>
      </div>
    </section>
  );
}

function ProjectShowcase() {
  return (
    <Card className='border-border mx-auto max-w-5xl overflow-hidden rounded-xl shadow-xl'>
      <CardHeader className='border-border flex-row items-center justify-between border-b px-5 py-4'>
        <div className='flex items-center gap-3'>
          <span className='bg-primary/10 text-primary flex size-9 items-center justify-center rounded-lg'>
            <Icons.workspace className='motion-safe:animate-[marketing-float_4s_ease-in-out_infinite]' />
          </span>
          <div>
            <CardTitle className='text-sm'>智慧社区 AI 治理项目</CardTitle>
            <CardDescription className='mt-0.5 text-xs'>项目响应进度</CardDescription>
          </div>
        </div>
        <span className='text-primary hidden items-center gap-1.5 text-xs sm:flex'>
          <span className='bg-primary size-1.5 motion-safe:animate-pulse rounded-full' />
          响应中
        </span>
      </CardHeader>
      <CardContent className='grid gap-5 p-5 md:grid-cols-[1.35fr_0.65fr]'>
        <div className='flex flex-col gap-4'>
          <div className='border-border bg-muted/20 rounded-lg border p-4'>
            <div className='flex items-center justify-between'>
              <p className='text-muted-foreground text-xs'>方案准备度</p>
              <p className='text-primary text-sm font-medium'>72%</p>
            </div>
            <div className='bg-border mt-3 h-2 overflow-hidden rounded-full'>
              <div className='bg-primary h-full w-[72%] rounded-full' />
            </div>
            <div className='mt-5 grid grid-cols-3 gap-3'>
              <ShowcaseStat value='18' label='关键要求' />
              <ShowcaseStat value='12' label='已有依据' />
              <ShowcaseStat value='3' label='待补内容' alert />
            </div>
          </div>
          <div className='grid gap-3 sm:grid-cols-3'>
            <ShowcaseTile icon={Icons.post} title='项目资料' value='5 份已归档' />
            <ShowcaseTile icon={Icons.forms} title='待确认' value='2 项需要复核' />
            <ShowcaseTile icon={Icons.fileTypeDoc} title='方案版本' value='1 版进行中' />
          </div>
        </div>
        <div className='border-border bg-muted/10 rounded-lg border p-4'>
          <div className='flex items-center justify-between'>
            <p className='text-muted-foreground text-xs'>响应进度</p>
            <Icons.moreHorizontal className='text-muted-foreground' />
          </div>
          <div className='mt-5 flex flex-col gap-5'>
            <ShowcaseStep title='整理项目资料' done />
            <ShowcaseStep title='确认关键要求' done />
            <ShowcaseStep title='起草方案内容' active />
            <ShowcaseStep title='团队确认' />
          </div>
        </div>
      </CardContent>
      <CardFooter className='border-border text-muted-foreground flex items-center gap-2 border-t px-5 py-3 text-xs'>
        <Icons.badgeCheck className='text-primary motion-safe:animate-[marketing-check-pop_500ms_ease-out]' />{' '}
        每个关键判断，都有依据可查
      </CardFooter>
    </Card>
  );
}

function ShowcaseStat({
  value,
  label,
  alert = false
}: {
  value: string;
  label: string;
  alert?: boolean;
}) {
  return (
    <div>
      <p className={cn('text-xl font-semibold', alert ? 'text-destructive' : 'text-foreground')}>
        {value}
      </p>
      <p className='text-muted-foreground mt-1 text-[11px]'>{label}</p>
    </div>
  );
}

function ShowcaseTile({
  icon: Icon,
  title,
  value
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  value: string;
}) {
  return (
    <div className='border-border flex flex-col gap-3 rounded-lg border p-3'>
      <Icon className='text-primary motion-safe:animate-[marketing-float_4s_ease-in-out_infinite]' />
      <div>
        <p className='text-foreground text-xs font-medium'>{title}</p>
        <p className='text-muted-foreground mt-1 text-[11px]'>{value}</p>
      </div>
    </div>
  );
}

function ShowcaseStep({
  title,
  done = false,
  active = false
}: {
  title: string;
  done?: boolean;
  active?: boolean;
}) {
  return (
    <div className='flex items-center gap-3'>
      <span
        className={cn(
          'flex size-5 items-center justify-center rounded-full border',
          done
            ? 'border-primary bg-primary/10 text-primary'
            : active
              ? 'border-primary text-primary'
              : 'border-border text-muted-foreground'
        )}
      >
        {done ? (
          <Icons.check className='motion-safe:animate-[marketing-check-pop_500ms_ease-out]' />
        ) : active ? (
          <span className='bg-primary size-1.5 motion-safe:animate-pulse rounded-full' />
        ) : null}
      </span>
      <span className={cn('text-sm', done || active ? 'text-foreground' : 'text-muted-foreground')}>
        {title}
      </span>
      {active && <span className='text-primary ml-auto text-[11px]'>起草中</span>}
    </div>
  );
}

function ExamplesCarousel() {
  const [isInView, setIsInView] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => setIsInView(entry.isIntersecting), {
      threshold: 0.35
    });
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section
      ref={containerRef}
      className='mx-auto my-20 max-w-7xl px-5 lg:my-32 lg:px-8'
      id='workflow'
    >
      <div className='mx-auto max-w-3xl text-center'>
        <p className='text-primary font-mono text-xs tracking-[0.18em] uppercase'>怎么工作</p>
        <h2 className='text-foreground mt-3 text-3xl font-bold sm:text-4xl'>
          从招标文件，到更有把握的提交。
        </h2>
        <p className='text-muted-foreground mt-4 text-base leading-7'>从机会出现，到方案交付。</p>
      </div>
      <div className='mt-12 w-full overflow-hidden'>
        <div
          className={cn(
            'marketing-marquee-track flex w-max gap-4 px-2 pb-5 pt-3 sm:px-0',
            isInView && 'motion-safe:animate-[marketing-carousel_36s_linear_infinite]'
          )}
        >
          {[...examples, ...examples].map((example, index) => {
            const isDuplicate = index >= examples.length;
            return (
              <Link
                key={`${example.name}-${index}`}
                href={example.href}
                className='group shrink-0'
                aria-label={example.name}
                aria-hidden={isDuplicate || undefined}
                tabIndex={isDuplicate ? -1 : undefined}
              >
                <Card className='w-[280px] overflow-hidden rounded-xl transition-all duration-300 group-hover:-translate-y-1 group-hover:shadow-lg sm:w-[340px] md:w-[390px]'>
                  <CardContent className='p-0'>
                    <ExampleSurface kind={example.surface} />
                    <div className='p-5'>
                      <p className='text-foreground font-semibold'>{example.name}</p>
                      <p className='text-muted-foreground mt-1 text-xs leading-5'>
                        {example.description}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function ExampleSurface({ kind }: { kind: (typeof examples)[number]['surface'] }) {
  if (kind === 'agent')
    return (
      <div className='bg-muted/30 grid aspect-video grid-cols-[0.32fr_0.68fr] gap-px'>
        <div className='bg-card p-3'>
          <div className='bg-primary/10 h-2 w-16 rounded motion-safe:animate-[marketing-width-pulse_3s_ease-in-out_infinite]' />
          <div className='mt-5 flex flex-col gap-2'>
            <span className='bg-muted h-2 rounded' />
            <span className='bg-muted h-2 w-4/5 rounded' />
            <span className='bg-muted h-2 w-3/5 rounded' />
          </div>
        </div>
        <div className='bg-card p-4'>
          <span className='text-primary text-[10px]'>AI 助手</span>
          <div className='mt-6 flex flex-col gap-3'>
            <span className='bg-muted h-3 w-4/5 rounded' />
            <span className='bg-primary/15 h-16 rounded-lg motion-safe:animate-[marketing-panel-breathe_4s_ease-in-out_infinite]' />
            <span className='bg-muted h-3 w-3/5 rounded' />
          </div>
        </div>
      </div>
    );
  if (kind === 'radar')
    return (
      <div className='bg-card relative aspect-video overflow-hidden p-5'>
        <div className='flex items-center justify-between'>
          <span className='text-foreground text-xs font-semibold'>机会雷达</span>
          <span className='text-primary flex items-center gap-1.5 text-[10px]'>
            <Icons.radar className='motion-safe:animate-[marketing-radar-sweep_4s_linear_infinite]' />
            持续更新
          </span>
        </div>
        <div className='mt-7 grid grid-cols-[0.58fr_0.42fr] gap-4'>
          <div className='border-border rounded-lg border p-3'>
            <div className='border-primary/30 relative aspect-square rounded-full border'>
              <div className='border-primary/20 absolute inset-[18%] rounded-full border' />
              <span className='bg-primary/20 absolute inset-[7%] rounded-full motion-safe:animate-[marketing-radar-pulse_3s_ease-out_infinite]' />
              <span className='bg-primary absolute top-1/2 left-1/2 z-10 size-2 -translate-1/2 rounded-full' />
              <span className='bg-primary/70 absolute top-1/2 left-1/2 h-px w-1/2 origin-left motion-safe:animate-[marketing-radar-sweep_4s_linear_infinite]' />
            </div>
          </div>
          <div className='flex flex-col gap-2'>
            <span className='bg-primary/15 h-8 rounded' />
            <span className='bg-muted h-8 rounded' />
            <span className='bg-muted h-8 rounded' />
          </div>
        </div>
      </div>
    );
  if (kind === 'review')
    return (
      <div className='bg-card aspect-video p-5'>
        <div className='flex items-center justify-between'>
          <span className='text-foreground text-xs font-semibold'>审核中心</span>
          <Icons.badgeCheck className='text-primary motion-safe:animate-[marketing-check-pop_500ms_ease-out]' />
        </div>
        <div className='mt-6 flex flex-col gap-3'>
          <div className='border-border flex items-center gap-3 rounded-lg border p-3'>
            <span className='bg-primary/10 text-primary flex size-6 items-center justify-center rounded'>
              <Icons.badgeCheck className='motion-safe:animate-[marketing-check-pop_500ms_ease-out]' />
            </span>
            <span className='bg-muted h-2 flex-1 rounded' />
          </div>
          <div className='border-destructive/30 flex items-center gap-3 rounded-lg border p-3'>
            <span className='bg-destructive/10 text-destructive flex size-6 items-center justify-center rounded'>
              <Icons.warning />
            </span>
            <span className='bg-muted h-2 flex-1 rounded' />
          </div>
        </div>
      </div>
    );
  return (
    <div className='bg-card aspect-video p-5'>
      <div className='flex items-center justify-between'>
        <span className='text-foreground text-xs font-semibold'>项目资料</span>
        <Icons.workspace className='text-primary motion-safe:animate-[marketing-float_4s_ease-in-out_infinite]' />
      </div>
      <div className='mt-6 grid grid-cols-3 gap-3'>
        <div className='bg-primary/10 h-24 rounded-lg' />
        <div className='bg-muted h-24 rounded-lg' />
        <div className='bg-muted h-24 rounded-lg' />
      </div>
      <div className='mt-4 flex gap-2'>
        <span className='bg-muted h-2 w-2/5 rounded' />
        <span className='bg-primary/20 h-2 w-1/5 rounded' />
      </div>
    </div>
  );
}

function HighlightedFeature() {
  return (
    <section className='py-20 sm:py-32'>
      <div className='mx-auto grid max-w-7xl items-center gap-12 px-5 lg:grid-cols-2 lg:gap-24 lg:px-8'>
        <div className='order-2 lg:order-1'>
          <p className='text-primary font-mono text-xs tracking-[0.18em] uppercase'>从资料到方案</p>
          <h2 className='text-foreground mt-4 text-3xl leading-tight font-bold sm:text-5xl'>
            让团队把时间花在赢单上。
          </h2>
          <p className='text-muted-foreground mt-5 max-w-xl text-base leading-7'>
            把繁琐的资料整理和重复核对，变成一条清晰的响应路径。
          </p>
          <ul className='mt-8 flex flex-col gap-4 text-sm'>
            <li className='flex items-start gap-3'>
              <Icons.check className='text-primary mt-0.5 shrink-0' />
              看清机会是否值得跟进
            </li>
            <li className='flex items-start gap-3'>
              <Icons.check className='text-primary mt-0.5 shrink-0' />
              知道还缺什么
            </li>
            <li className='flex items-start gap-3'>
              <Icons.check className='text-primary mt-0.5 shrink-0' />
              让每一版方案都有依据
            </li>
          </ul>
          <Link className={cn(buttonVariants({ variant: 'outline' }), 'mt-9')} href='/projects'>
            进入项目工作区 <Icons.arrowRight data-icon='inline-end' />
          </Link>
        </div>
        <div className='order-1 lg:order-2'>
          <ProjectWorkspaceFeature />
        </div>
      </div>
    </section>
  );
}

function ProjectWorkspaceFeature() {
  return (
    <Card className='border-border overflow-hidden rounded-xl shadow-lg'>
      <CardHeader className='border-border border-b'>
        <CardTitle className='text-base'>一条清晰的响应路径</CardTitle>
        <CardDescription>从机会判断，到方案交付</CardDescription>
      </CardHeader>
      <CardContent className='p-5'>
        <div className='flex flex-col gap-4'>
          {[
            ['机会判断', '值得跟进，立即进入项目', Icons.post],
            ['要求确认', '18 条要求，3 项待补', Icons.forms],
            ['方案起草', '12 条依据，继续推进', Icons.badgeCheck],
            ['团队确认', '一版方案，清楚交付', Icons.fileTypeDoc]
          ].map(([title, detail, Icon]) => (
            <div
              key={title as string}
              className='border-border flex items-center gap-3 rounded-lg border p-3'
            >
              <span className='bg-primary/10 text-primary flex size-8 items-center justify-center rounded-md'>
                <Icon />
              </span>
              <span className='min-w-0 flex-1'>
                <span className='text-foreground block text-sm font-medium'>{title as string}</span>
                <span className='text-muted-foreground mt-1 block text-xs'>{detail as string}</span>
              </span>
              <Icons.arrowRight className='text-muted-foreground' />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function FeaturesGrid() {
  return (
    <section className='mx-auto my-20 max-w-7xl px-5 sm:my-32 lg:px-8' id='features'>
      <div className='mx-auto max-w-3xl text-center'>
        <p className='text-primary font-mono text-xs tracking-[0.18em] uppercase'>
          一套工作台，覆盖全程
        </p>
        <h2 className='text-foreground mt-3 text-3xl font-bold sm:text-4xl'>
          从机会出现，到方案交付。
        </h2>
        <p className='text-muted-foreground mt-4 text-base leading-7'>
          每一步都有依据，每个人都有下一步。
        </p>
      </div>
      <div className='mt-12 grid auto-rows-[minmax(150px,auto)] grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6'>
        {featureItems.map((feature) => {
          const Icon = feature.icon;
          const sizeClass =
            feature.size === 'small'
              ? 'col-span-1'
              : feature.size === 'large'
                ? 'col-span-2 row-span-2'
                : 'col-span-2';
          return (
            <Link
              key={feature.name}
              href={feature.href}
              aria-label={feature.name}
              className={cn('block h-full', sizeClass)}
            >
              <Card className='group border-border h-full rounded-xl transition-all duration-300 hover:-translate-y-1 hover:shadow-lg'>
                <CardContent className='flex h-full flex-col items-center justify-center p-5 text-center'>
                  <span className='bg-primary/10 text-primary flex size-11 items-center justify-center rounded-xl transition-transform duration-300 group-hover:-translate-y-1 group-hover:rotate-3 motion-reduce:transition-none'>
                    <Icon className='transition-transform duration-300 group-hover:scale-110 motion-reduce:transition-none' />
                  </span>
                  <CardTitle className='text-foreground mt-4'>{feature.name}</CardTitle>
                  <CardDescription className='mt-2 text-xs leading-5'>
                    {feature.description}
                  </CardDescription>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

function UseCases() {
  return (
    <section className='py-20 sm:py-32' id='teams'>
      <div className='mx-auto max-w-7xl px-5 lg:px-8'>
        <div className='mx-auto max-w-3xl text-center'>
          <p className='text-primary font-mono text-xs tracking-[0.18em] uppercase'>
            为投标团队设计
          </p>
          <h2 className='text-foreground mt-3 text-3xl font-bold sm:text-4xl'>
            每个人，都能更快推进。
          </h2>
        </div>
        <div className='mt-12 grid gap-4 md:grid-cols-3'>
          {roleSurfaces.map((item) => {
            return (
              <Card key={item.role} className='border-border rounded-xl'>
                <CardHeader>
                  <div className='flex items-center justify-between'>
                    <span className='text-muted-foreground text-xs'>{item.role}</span>
                    <RoleIcon role={item.role} />
                  </div>
                  <CardTitle className='mt-4'>{item.title}</CardTitle>
                  <CardDescription className='leading-6'>{item.detail}</CardDescription>
                </CardHeader>
                <CardFooter className='text-primary gap-2 text-xs'>
                  <Link href={item.href} className='inline-flex items-center gap-2 hover:underline'>
                    查看工作区 <Icons.arrowRight />
                  </Link>
                </CardFooter>
              </Card>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function RoleIcon({ role }: { role: string }) {
  if (role === '投标负责人') return <Icons.myWork className='text-primary' />;
  if (role === '方案工程师') return <Icons.edit className='text-primary' />;
  return <Icons.badgeCheck className='text-primary' />;
}

function Faq() {
  return (
    <section
      className='mx-auto mt-20 max-w-4xl px-5 pb-20 sm:mt-32 sm:pb-32 lg:max-w-7xl lg:px-8'
      id='faq'
    >
      <div className='mx-auto max-w-3xl text-center'>
        <p className='text-primary font-mono text-xs tracking-[0.18em] uppercase'>还有疑问？</p>
        <h2 className='text-foreground mt-3 text-3xl font-bold sm:text-4xl'>
          你关心的，我们直接回答。
        </h2>
      </div>
      <Accordion multiple className='mx-auto mt-12 w-full max-w-4xl'>
        {[
          ['我的资料安全吗？', '项目资料按工作区管理，只有受邀成员可以访问。'],
          ['生成的内容有依据吗？', '可以关联项目来源，关键内容有据可查，缺口也会明确标出。'],
          ['团队可以一起工作吗？', '可以。项目、成员、审核和版本都在同一个工作区里。'],
          ['第一次使用从哪里开始？', '创建工作区，放入一份招标资料，就能开始一次响应。']
        ].map(([question, answer], index) => (
          <AccordionItem
            key={question}
            value={`faq-${index}`}
            className='border-border hover:bg-muted/20 rounded-lg border px-6 py-2 transition-colors duration-200'
          >
            <AccordionTrigger className='text-foreground py-5 text-left text-sm font-semibold hover:no-underline'>
              {question}
            </AccordionTrigger>
            <AccordionContent className='text-muted-foreground pb-5 text-sm leading-6'>
              {answer}
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </section>
  );
}

function OpenSaasFooter() {
  return (
    <footer className='border-border mx-auto mt-6 max-w-7xl border-t px-5 py-16 lg:px-8'>
      <div className='flex flex-col gap-12 sm:flex-row sm:items-start sm:justify-between'>
        <div>
          <BrandLogo />
          <p className='text-muted-foreground mt-4 max-w-xs text-sm leading-6'>
            让投标响应更有把握。
          </p>
        </div>
        <div className='grid grid-cols-2 gap-16'>
          <div>
            <h3 className='text-foreground text-sm font-semibold'>产品</h3>
            <ul className='text-muted-foreground mt-5 flex flex-col gap-3 text-sm'>
              <li>
                <Link className='hover:text-foreground' href='/projects'>
                  项目
                </Link>
              </li>
              <li>
                <Link className='hover:text-foreground' href='/agent'>
                  AI 助手
                </Link>
              </li>
              <li>
                <Link className='hover:text-foreground' href='/radar'>
                  招标雷达
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h3 className='text-foreground text-sm font-semibold'>开始使用</h3>
            <ul className='text-muted-foreground mt-5 flex flex-col gap-3 text-sm'>
              <li>
                <Link className='hover:text-foreground' href='/auth/sign-in'>
                  登录
                </Link>
              </li>
              <li>
                <Link className='hover:text-foreground' href='/auth/sign-up'>
                  开始一次响应
                </Link>
              </li>
              <li>
                <Link className='hover:text-foreground' href='/docs'>
                  文档
                </Link>
              </li>
            </ul>
          </div>
        </div>
      </div>
      <div className='border-border text-muted-foreground mt-16 flex flex-col gap-3 border-t pt-5 text-xs sm:flex-row sm:items-center sm:justify-between'>
        <span>© {new Date().getFullYear()} BidPilot</span>
        <span>从第一份资料，到最后一版方案。</span>
      </div>
    </footer>
  );
}
