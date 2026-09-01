'use client';

import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { UserAvatarProfile } from '@/components/user-avatar-profile';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import { Icons } from '@/components/icons';

export function UserNav() {
  const router = useRouter();
  const { user, logout } = useAuth();
  if (!user) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant='ghost' size='icon' className='rounded-full' aria-label='打开账户菜单' />
        }
      >
        <UserAvatarProfile user={user} />
      </DropdownMenuTrigger>
      <DropdownMenuContent className='w-56' align='end' sideOffset={8}>
        <DropdownMenuLabel className='font-normal'>
          <div className='flex min-w-0 flex-col gap-1'>
            <span className='truncate font-medium'>{user.display_name}</span>
            <span className='text-muted-foreground truncate text-xs'>{user.email}</span>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => router.push('/account')}>
          <Icons.account className='size-4' />
          账户
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => router.push('/settings/providers')}>
          <Icons.settings className='size-4' />
          设置
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => void logout().then(() => router.replace('/auth/sign-in'))}>
          <Icons.logout className='size-4' />
          退出登录
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
