'use client';

import { SidebarTrigger } from '@/components/ui/sidebar';
import { Separator } from '@/components/ui/separator';
import { Breadcrumbs } from '@/components/breadcrumbs';
import { ThemeModeToggle } from '@/components/themes/theme-mode-toggle';

export default function Header() {
  return (
    <header className='bg-background/80 sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between gap-2 border-b backdrop-blur-md'>
      <div className='flex min-w-0 items-center gap-2 px-4'>
        <SidebarTrigger className='-ml-1' aria-label='展开或收起侧栏' />
        <Separator orientation='vertical' className='mr-1 h-4' />
        <Breadcrumbs />
      </div>
      <div className='flex shrink-0 items-center gap-1 px-4'>
        <ThemeModeToggle />
      </div>
    </header>
  );
}
