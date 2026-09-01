'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Icons } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/**
 * Adapted from ixartz/SaaS-Boilerplate's CenteredMenu. The route links and
 * visual primitives stay local to BidPilot; the responsive menu composition
 * remains the upstream pattern.
 */
export const CenteredMenu = (props: {
  logo: React.ReactNode;
  children: React.ReactNode;
  rightMenu: React.ReactNode;
}) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const navClass = cn('max-lg:w-full max-lg:bg-secondary max-lg:p-5', {
    'max-lg:hidden': !isMenuOpen
  });

  return (
    <div className='flex flex-wrap items-center justify-between'>
      <Link href='/' aria-label='BidPilot 首页'>
        {props.logo}
      </Link>

      <div className='lg:hidden'>
        <Button
          type='button'
          variant='ghost'
          size='icon'
          aria-expanded={isMenuOpen}
          aria-label={isMenuOpen ? '关闭主导航' : '打开主导航'}
          onClick={() => setIsMenuOpen((current) => !current)}
        >
          {isMenuOpen ? (
            <Icons.close data-icon='inline-start' />
          ) : (
            <Icons.menu data-icon='inline-start' />
          )}
        </Button>
      </div>

      <nav className={cn('rounded-t-xl max-lg:mt-2', navClass)} aria-label='主导航'>
        <ul className='flex gap-x-6 gap-y-1 text-lg font-medium max-lg:flex-col max-lg:[&_a]:inline-block max-lg:[&_a]:w-full [&_a:hover]:opacity-70'>
          {props.children}
        </ul>
      </nav>

      <div className={cn('rounded-b-xl max-lg:border-t max-lg:border-border', navClass)}>
        <ul className='flex flex-row items-center gap-x-1.5 text-lg font-medium [&_a:hover]:opacity-70'>
          {props.rightMenu}
        </ul>
      </div>
    </div>
  );
};
