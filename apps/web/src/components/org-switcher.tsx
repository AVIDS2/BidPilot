'use client';

import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { Icons } from '@/components/icons';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar
} from '@/components/ui/sidebar';

export function OrgSwitcher() {
  const { state, isMobile, toggleSidebar } = useSidebar();
  const router = useRouter();
  const { user } = useAuth();
  const workspaceName = user?.org_slug || '个人工作区';

  if (state === 'collapsed' && !isMobile) {
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            size='lg'
            onClick={toggleSidebar}
            aria-label='展开工作区导航'
            tooltip='展开工作区导航'
          >
            <div className='bg-sidebar-primary text-sidebar-primary-foreground flex size-8 shrink-0 items-center justify-center rounded-lg'>
              <Icons.workspace className='size-4' />
            </div>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    );
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton
                size='lg'
                className='data-popup-open:bg-sidebar-accent data-popup-open:text-sidebar-accent-foreground'
              />
            }
          >
            <div className='bg-sidebar-primary text-sidebar-primary-foreground flex size-8 shrink-0 items-center justify-center rounded-lg'>
              <Icons.workspace className='size-4' />
            </div>
            <div
              className={
                state === 'collapsed'
                  ? 'invisible max-w-0 overflow-hidden opacity-0'
                  : 'grid min-w-0 flex-1 text-left text-sm leading-tight'
              }
            >
              <span className='truncate font-semibold'>BidPilot</span>
              <span className='text-muted-foreground truncate text-xs'>{workspaceName}</span>
            </div>
            <Icons.chevronsUpDown
              className={state === 'collapsed' ? 'invisible' : 'ml-auto size-4'}
            />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className='min-w-56'
            align='start'
            side={isMobile ? 'bottom' : 'right'}
            sideOffset={6}
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel className='text-muted-foreground text-xs'>
                当前工作区
              </DropdownMenuLabel>
              <DropdownMenuItem className='gap-2' onClick={() => router.push('/projects')}>
                <Icons.workspace className='size-4' />
                <span className='truncate'>{workspaceName}</span>
                <Icons.check className='text-primary ml-auto size-4' />
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem onClick={() => router.push('/account')}>
                <Icons.settings className='size-4' />
                工作区设置
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
