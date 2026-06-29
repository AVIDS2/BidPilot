import * as React from "react";
import { cn } from "@/lib/utils";

type BrandMarkProps = React.SVGProps<SVGSVGElement> & {
  decorative?: boolean;
  title?: string;
};

export function BrandMark({
  decorative = false,
  title = "BidPilot",
  className,
  ...props
}: BrandMarkProps) {
  const rawId = React.useId().replace(/:/g, "");
  const shellGradient = `bp-shell-${rawId}`;
  const paperGradient = `bp-paper-${rawId}`;
  const accentGradient = `bp-accent-${rawId}`;
  const titleId = `bp-title-${rawId}`;

  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      role={decorative ? undefined : "img"}
      aria-hidden={decorative ? true : undefined}
      aria-labelledby={decorative ? undefined : titleId}
      className={cn("shrink-0", className)}
      {...props}
    >
      {!decorative && <title id={titleId}>{title}</title>}
      <defs>
        <linearGradient id={shellGradient} x1="8" y1="4" x2="58" y2="62" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#111827" />
          <stop offset="0.48" stopColor="#05070A" />
          <stop offset="1" stopColor="#162019" />
        </linearGradient>
        <linearGradient id={paperGradient} x1="16" y1="10" x2="48" y2="54" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#F8FAFC" />
          <stop offset="0.58" stopColor="#CBD5E1" />
          <stop offset="1" stopColor="#7F8B99" />
        </linearGradient>
        <linearGradient id={accentGradient} x1="17" y1="45" x2="49" y2="16" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#A3E635" />
          <stop offset="0.52" stopColor="#34D399" />
          <stop offset="1" stopColor="#2DD4BF" />
        </linearGradient>
      </defs>

      <rect x="3.5" y="3.5" width="57" height="57" rx="18" fill={`url(#${shellGradient})`} />
      <rect x="4.25" y="4.25" width="55.5" height="55.5" rx="17.25" stroke="white" strokeOpacity="0.12" strokeWidth="1.5" />
      <path
        d="M18.5 12.5H39.8L50.5 23.2V49.5C50.5 51.2 49.2 52.5 47.5 52.5H18.5C16.8 52.5 15.5 51.2 15.5 49.5V15.5C15.5 13.8 16.8 12.5 18.5 12.5Z"
        fill={`url(#${paperGradient})`}
        fillOpacity="0.92"
      />
      <path
        d="M39.5 12.8V21.2C39.5 22.8 40.8 24.1 42.4 24.1H50.1"
        stroke="#F8FAFC"
        strokeOpacity="0.72"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M23 24.5H35.5M23 31H39M23 37.5H32.5" stroke="#111827" strokeOpacity="0.34" strokeWidth="2" strokeLinecap="round" />
      <path
        d="M18.8 45.2C25.2 36.3 30.5 38.9 35.7 30.1C39.2 24.1 43.5 20.2 49.2 17.5"
        stroke={`url(#${accentGradient})`}
        strokeWidth="3.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M43.1 16.4L49.8 17.1L47.7 23.6" stroke={`url(#${accentGradient})`} strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="25.6" cy="37.9" r="2.4" fill="#05070A" stroke="#A3E635" strokeWidth="1.8" />
      <circle cx="36.3" cy="29.1" r="2.4" fill="#05070A" stroke="#34D399" strokeWidth="1.8" />
      <path d="M12.5 51.5L20.7 43.3" stroke="#A3E635" strokeOpacity="0.36" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export function BrandLogo({
  className,
  markClassName,
  textClassName,
}: {
  className?: string;
  markClassName?: string;
  textClassName?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <BrandMark decorative className={cn("size-8", markClassName)} />
      <span className={cn("font-semibold tracking-[-0.045em] text-current", textClassName)}>
        BidPilot
      </span>
    </span>
  );
}
