'use client';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';

export default function Error({
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className='bg-muted/20 flex min-h-svh items-center justify-center px-5 py-10'>
      <Alert className='max-w-md' variant='destructive'>
        <AlertTitle>页面暂时无法打开</AlertTitle>
        <AlertDescription className='mt-1'>
          请重新加载当前页面。如果问题持续存在，请查看运行记录或联系管理员。
        </AlertDescription>
        <Button className='mt-4' variant='outline' onClick={() => reset()}>
          重新加载
        </Button>
      </Alert>
    </main>
  );
}
