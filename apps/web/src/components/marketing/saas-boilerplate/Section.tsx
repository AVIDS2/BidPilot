import { cn } from '@/lib/utils';

export const Section = (props: {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  description?: string;
  className?: string;
  id?: string;
}) => (
  <section id={props.id} className={cn('@container px-3 py-16', props.className)}>
    {(props.title || props.subtitle || props.description) && (
      <div className='mx-auto mb-12 max-w-3xl text-center'>
        {props.subtitle && <p className='text-primary text-sm font-bold'>{props.subtitle}</p>}

        {props.title && <h2 className='mt-1 text-pretty text-3xl font-bold'>{props.title}</h2>}

        {props.description && (
          <p className='text-muted-foreground mt-2 text-pretty text-lg'>{props.description}</p>
        )}
      </div>
    )}

    <div className='mx-auto max-w-5xl'>{props.children}</div>
  </section>
);
