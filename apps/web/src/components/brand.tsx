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
  const compassGradient = `bp-compass-${rawId}`;
  const routeGradient = `bp-route-${rawId}`;
  const targetGradient = `bp-target-${rawId}`;
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
          <stop offset="0" stopColor="#1B2330" />
          <stop offset="0.48" stopColor="#05070A" />
          <stop offset="1" stopColor="#0C1D14" />
        </linearGradient>
        <linearGradient id={compassGradient} x1="19" y1="47" x2="51" y2="17" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#A3E635" />
          <stop offset="0.48" stopColor="#5BE878" />
          <stop offset="1" stopColor="#2DD4BF" />
        </linearGradient>
        <linearGradient id={routeGradient} x1="17" y1="45" x2="49" y2="18" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#A3E635" />
          <stop offset="0.52" stopColor="#7DD3FC" />
          <stop offset="1" stopColor="#2DD4BF" />
        </linearGradient>
        <radialGradient id={targetGradient} cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(47.5 18.5) rotate(94.2) scale(13.5)">
          <stop offset="0" stopColor="#F8FAFC" />
          <stop offset="0.42" stopColor="#A3E635" />
          <stop offset="1" stopColor="#2DD4BF" stopOpacity="0" />
        </radialGradient>
      </defs>

      <rect x="3.5" y="3.5" width="57" height="57" rx="18" fill={`url(#${shellGradient})`} />
      <rect x="4.25" y="4.25" width="55.5" height="55.5" rx="17.25" stroke="white" strokeOpacity="0.12" strokeWidth="1.5" />
      <path d="M14 21H50M14 32H50M14 43H50M22 13V51M33 13V51M44 13V51" stroke="#F8FAFC" strokeOpacity="0.055" strokeWidth="1" />
      <path
        d="M15.4 47.1C24.1 36.8 28.1 39.3 34.2 30.4C38.7 23.8 42.6 20 49.4 16.4"
        stroke={`url(#${routeGradient})`}
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="47.7" cy="18.3" r="13" fill={`url(#${targetGradient})`} opacity="0.6" />
      <circle cx="47.7" cy="18.3" r="7.7" stroke="#F8FAFC" strokeOpacity="0.24" strokeWidth="1.3" />
      <circle cx="47.7" cy="18.3" r="3.2" fill="#F8FAFC" fillOpacity="0.92" />
      <path
        d="M19.5 48.5L30.3 16.8C30.8 15.2 33 15.1 33.7 16.6L39.8 30.9L50.6 19.3C51.8 18 53.8 19.3 53.2 21L42.3 49C41.7 50.7 39.4 50.9 38.6 49.3L32.3 36.9L21.8 50.4C20.7 51.8 18.9 50.1 19.5 48.5Z"
        fill={`url(#${compassGradient})`}
      />
      <path
        d="M30.9 18.3L32.3 36.9M39.8 30.9L32.3 36.9M42.2 48.6L39.8 30.9"
        stroke="#03120B"
        strokeOpacity="0.38"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="20.5" cy="46.2" r="2.6" fill="#05070A" stroke="#A3E635" strokeWidth="1.8" />
      <circle cx="34.2" cy="30.4" r="2.6" fill="#05070A" stroke="#7DD3FC" strokeWidth="1.8" />
    </svg>
  );
}

export function AgentMark({
  decorative = false,
  title = "BidPilot AI",
  className,
  ...props
}: BrandMarkProps) {
  const rawId = React.useId().replace(/:/g, "");
  const shellGradient = `bp-agent-shell-${rawId}`;
  const needleGradient = `bp-agent-needle-${rawId}`;
  const ringGradient = `bp-agent-ring-${rawId}`;
  const titleId = `bp-agent-title-${rawId}`;

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
        <linearGradient id={shellGradient} x1="8" y1="5" x2="58" y2="60" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#102337" />
          <stop offset="0.5" stopColor="#061018" />
          <stop offset="1" stopColor="#0B2017" />
        </linearGradient>
        <linearGradient id={needleGradient} x1="18" y1="47" x2="48" y2="15" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#A3E635" />
          <stop offset="0.5" stopColor="#5BE878" />
          <stop offset="1" stopColor="#38BDF8" />
        </linearGradient>
        <linearGradient id={ringGradient} x1="14" y1="45" x2="50" y2="18" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#A3E635" />
          <stop offset="0.42" stopColor="#2DD4BF" />
          <stop offset="1" stopColor="#7DD3FC" />
        </linearGradient>
      </defs>

      <rect x="3.5" y="3.5" width="57" height="57" rx="20" fill={`url(#${shellGradient})`} />
      <rect x="4.25" y="4.25" width="55.5" height="55.5" rx="19.25" stroke="white" strokeOpacity="0.13" strokeWidth="1.5" />
      <path
        d="M15.2 38.1C21.2 48.8 36.2 52 46 43.8C55.4 35.9 54.9 21.3 45.1 14.2"
        stroke={`url(#${ringGradient})`}
        strokeOpacity="0.66"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      <path
        d="M48.7 14.4L44.8 13.6L45.8 17.4"
        stroke="#7DD3FC"
        strokeOpacity="0.82"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M18.4 47.2L29.4 16.5C30 14.9 32.2 14.9 32.9 16.4L38.7 30.5L49 19.7C50.2 18.4 52.2 19.7 51.5 21.4L41.5 49C40.9 50.7 38.6 50.9 37.8 49.2L31.6 36.6L20.8 49.1C19.6 50.5 17.8 48.8 18.4 47.2Z"
        fill={`url(#${needleGradient})`}
      />
      <path d="M31.6 36.6L29.9 18.1M31.6 36.6L38.7 30.5M38.7 30.5L41.4 48.4" stroke="#04130D" strokeOpacity="0.42" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="31.8" cy="36.4" r="3.6" fill="#061018" stroke="#F8FAFC" strokeOpacity="0.84" strokeWidth="1.6" />
      <circle cx="31.8" cy="36.4" r="1.35" fill="#A3E635" />
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
