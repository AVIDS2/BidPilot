export const CenteredHero = (props: {
  banner: React.ReactNode;
  title: React.ReactNode;
  description: string;
  buttons: React.ReactNode;
}) => (
  <>
    <div className='text-center'>{props.banner}</div>

    <h1 className='mt-3 text-center text-pretty text-4xl font-bold tracking-tight sm:text-5xl'>
      {props.title}
    </h1>

    <p
      className='
      text-muted-foreground mx-auto mt-5 max-w-3xl text-center text-pretty text-xl
    '
    >
      {props.description}
    </p>

    <div
      className='
      mt-8 flex justify-center gap-x-5 gap-y-3
      max-sm:flex-col
    '
    >
      {props.buttons}
    </div>
  </>
);
