import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';

interface UserAvatarProfileProps {
  className?: string;
  showInfo?: boolean;
  user: {
    avatar_url?: string | null;
    display_name?: string | null;
    email?: string | null;
  } | null;
}

export function UserAvatarProfile({ className, showInfo = false, user }: UserAvatarProfileProps) {
  const name = user?.display_name?.trim() || 'BidPilot 用户';
  const initials = name
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className='flex min-w-0 items-center gap-2'>
      <Avatar className={className}>
        <AvatarImage src={user?.avatar_url ?? undefined} alt={name} />
        <AvatarFallback className='rounded-lg'>{initials || 'BP'}</AvatarFallback>
      </Avatar>
      {showInfo && (
        <div className='grid min-w-0 flex-1 text-left text-sm leading-tight'>
          <span className='truncate font-semibold'>{name}</span>
          <span className='text-muted-foreground truncate text-xs'>{user?.email || ''}</span>
        </div>
      )}
    </div>
  );
}
