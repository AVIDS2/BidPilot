import { buttonVariants } from '@/components/ui/button';
import { Icons } from '@/components/icons';
import { cn } from '@/lib/utils';

export default function CtaGithub() {
  return (
    <a
      className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'group hidden sm:flex')}
      aria-label='View on GitHub'
      href='https://github.com/Kiranism/next-shadcn-dashboard-starter'
      rel='noopener noreferrer'
      target='_blank'
    >
      <Icons.github className='transition-transform duration-300 group-hover:animate-bounce' />
    </a>
  );
}
