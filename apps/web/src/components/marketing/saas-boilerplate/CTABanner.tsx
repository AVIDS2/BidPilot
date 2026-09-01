export const CTABanner = (props: {
  title: string;
  description: string;
  buttons: React.ReactNode;
}) => (
  <div className='bg-primary text-primary-foreground rounded-xl px-6 py-10 text-center'>
    <h2 className='text-pretty text-3xl font-bold'>{props.title}</h2>

    <p className='text-primary-foreground/80 mt-2 text-pretty text-lg font-medium'>
      {props.description}
    </p>

    <div className='mt-6'>{props.buttons}</div>
  </div>
);
