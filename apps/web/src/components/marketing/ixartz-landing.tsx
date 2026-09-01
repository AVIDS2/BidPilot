import type { ReactNode } from 'react';

/**
 * Adapted from ixartz/Next-JS-Landing-Page-Starter-Template (MIT).
 * BidPilot owns the copy, data boundary and actions.
 */
export function IxartzSection({
  children,
  title,
  description,
  className = '',
  id
}: {
  children: ReactNode;
  title?: string;
  description?: string;
  className?: string;
  id?: string;
}) {
  return (
    <section className={`mx-auto max-w-7xl px-5 py-16 lg:px-8 ${className}`} id={id}>
      {(title || description) && (
        <div className='mb-12 text-center'>
          {title && <h2 className='text-3xl font-semibold tracking-tight'>{title}</h2>}
          {description && (
            <p className='text-muted-foreground mt-4 text-lg leading-7'>{description}</p>
          )}
        </div>
      )}
      {children}
    </section>
  );
}

export function IxartzHero({
  title,
  description,
  actions,
  children
}: {
  title: ReactNode;
  description: string;
  actions: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header>
      <h1 className='text-4xl leading-tight font-semibold tracking-tight sm:text-6xl'>{title}</h1>
      <p className='text-muted-foreground mt-6 max-w-xl text-lg leading-8'>{description}</p>
      <div className='mt-8 flex flex-wrap items-center gap-3'>{actions}</div>
      {children}
    </header>
  );
}
