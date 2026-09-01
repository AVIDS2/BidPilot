'use client';

import { useRouter } from 'next/navigation';
import { Icons } from '@/components/icons';
import { Button } from '@/components/ui/button';

export default function SearchInput() {
  const router = useRouter();
  return (
    <Button
      variant='outline'
      className='text-muted-foreground w-full justify-start font-normal shadow-none md:w-40 lg:w-64'
      onClick={() => router.push('/projects')}
      aria-label='打开项目搜索'
    >
      <Icons.search data-icon='inline-start' />
      搜索项目
    </Button>
  );
}
