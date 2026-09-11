import type { ReactNode } from 'react';

export function PageHeader({
  eyebrow,
  title,
  description,
  action
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className='flex flex-col gap-4 border-b px-5 py-6 xl:flex-row xl:items-end xl:justify-between lg:px-8'>
      <div className='min-w-0'>
        {eyebrow && <p className='text-primary mb-2 text-xs font-medium'>{eyebrow}</p>}
        <h1 className='text-2xl font-semibold tracking-tight'>{title}</h1>
        {description && (
          <p className='text-muted-foreground mt-2 max-w-2xl text-sm leading-6'>{description}</p>
        )}
      </div>
      {action && <div className='shrink-0'>{action}</div>}
    </div>
  );
}
