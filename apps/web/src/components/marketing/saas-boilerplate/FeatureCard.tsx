export const FeatureCard = (props: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) => (
  <div className='rounded-xl border border-border bg-background p-5'>
    <div className='bg-primary text-primary-foreground flex size-12 items-center justify-center rounded-lg p-2'>
      {props.icon}
    </div>

    <h3 className='mt-2 text-lg font-bold'>{props.title}</h3>

    <div className='border-primary/30 my-3 w-8 border-t' />

    <p className='text-muted-foreground mt-2'>{props.children}</p>
  </div>
);
