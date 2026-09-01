import * as React from 'react';
import Image from 'next/image';
import { cn } from '@/lib/utils';
import bidpilotLogo from '@/assets/bidpilot-logo.svg';

type BrandMarkProps = Omit<
  React.ComponentProps<typeof Image>,
  'src' | 'alt' | 'width' | 'height'
> & {
  decorative?: boolean;
  title?: string;
};

type AgentMarkProps = React.SVGProps<SVGSVGElement> & {
  decorative?: boolean;
  title?: string;
};

export function BrandMark({
  decorative = false,
  title = 'BidPilot',
  className,
  ...props
}: BrandMarkProps) {
  const logoSrc = typeof bidpilotLogo === 'string' ? bidpilotLogo : bidpilotLogo.src;
  return (
    <Image
      src={logoSrc}
      width={1024}
      height={1024}
      alt={decorative ? '' : title}
      aria-hidden={decorative ? true : undefined}
      className={cn('shrink-0 object-contain', className)}
      {...props}
    />
  );
}

export function AgentMark({
  decorative = false,
  title = 'BidPilot AI',
  className,
  ...props
}: AgentMarkProps) {
  const rawId = React.useId().replace(/:/g, '');
  const shellGradient = `bp-agent-shell-${rawId}`;
  const needleGradient = `bp-agent-needle-${rawId}`;
  const ringGradient = `bp-agent-ring-${rawId}`;
  const titleId = `bp-agent-title-${rawId}`;

  return (
    <svg
      viewBox='0 0 64 64'
      fill='none'
      role={decorative ? undefined : 'img'}
      aria-hidden={decorative ? true : undefined}
      aria-labelledby={decorative ? undefined : titleId}
      className={cn('shrink-0', className)}
      {...props}
    >
      {!decorative && <title id={titleId}>{title}</title>}
      <defs>
        <linearGradient
          id={shellGradient}
          x1='8'
          y1='5'
          x2='58'
          y2='60'
          gradientUnits='userSpaceOnUse'
        >
          <stop offset='0' stopColor='#102337' />
          <stop offset='0.5' stopColor='#061018' />
          <stop offset='1' stopColor='#0B2017' />
        </linearGradient>
        <linearGradient
          id={needleGradient}
          x1='18'
          y1='47'
          x2='48'
          y2='15'
          gradientUnits='userSpaceOnUse'
        >
          <stop offset='0' stopColor='#38BDF8' />
          <stop offset='0.5' stopColor='#8B5CF6' />
          <stop offset='1' stopColor='#D946EF' />
        </linearGradient>
        <linearGradient
          id={ringGradient}
          x1='14'
          y1='45'
          x2='50'
          y2='18'
          gradientUnits='userSpaceOnUse'
        >
          <stop offset='0' stopColor='#38BDF8' />
          <stop offset='0.42' stopColor='#6366F1' />
          <stop offset='1' stopColor='#D946EF' />
        </linearGradient>
      </defs>

      <rect x='3.5' y='3.5' width='57' height='57' rx='20' fill={`url(#${shellGradient})`} />
      <rect
        x='4.25'
        y='4.25'
        width='55.5'
        height='55.5'
        rx='19.25'
        stroke='white'
        strokeOpacity='0.13'
        strokeWidth='1.5'
      />
      <path
        d='M15.2 38.1C21.2 48.8 36.2 52 46 43.8C55.4 35.9 54.9 21.3 45.1 14.2'
        stroke={`url(#${ringGradient})`}
        strokeOpacity='0.66'
        strokeWidth='2.2'
        strokeLinecap='round'
      />
      <path
        d='M48.7 14.4L44.8 13.6L45.8 17.4'
        stroke='#7DD3FC'
        strokeOpacity='0.82'
        strokeWidth='2'
        strokeLinecap='round'
        strokeLinejoin='round'
      />
      <path
        d='M18.4 47.2L29.4 16.5C30 14.9 32.2 14.9 32.9 16.4L38.7 30.5L49 19.7C50.2 18.4 52.2 19.7 51.5 21.4L41.5 49C40.9 50.7 38.6 50.9 37.8 49.2L31.6 36.6L20.8 49.1C19.6 50.5 17.8 48.8 18.4 47.2Z'
        fill={`url(#${needleGradient})`}
      />
      <path
        d='M31.6 36.6L29.9 18.1M31.6 36.6L38.7 30.5M38.7 30.5L41.4 48.4'
        stroke='#04130D'
        strokeOpacity='0.42'
        strokeWidth='2'
        strokeLinecap='round'
        strokeLinejoin='round'
      />
      <circle
        cx='31.8'
        cy='36.4'
        r='3.6'
        fill='#061018'
        stroke='#F8FAFC'
        strokeOpacity='0.84'
        strokeWidth='1.6'
      />
      <circle cx='31.8' cy='36.4' r='1.35' fill='#38BDF8' />
    </svg>
  );
}

export function BrandLogo({
  className,
  markClassName,
  textClassName
}: {
  className?: string;
  markClassName?: string;
  textClassName?: string;
}) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <BrandMark decorative className={cn('size-8', markClassName)} />
      <span className={cn('font-semibold tracking-[-0.045em] text-current', textClassName)}>
        BidPilot
      </span>
    </span>
  );
}
