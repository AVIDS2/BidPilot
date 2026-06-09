import { type SVGProps } from "react";

export function UploadIllustration(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* Background circle */}
      <circle cx="100" cy="100" r="90" fill="var(--muted)" opacity="0.3" />

      {/* Upload area */}
      <rect
        x="50"
        y="70"
        width="100"
        height="80"
        rx="8"
        fill="var(--card)"
        stroke="var(--border)"
        strokeWidth="2"
        strokeDasharray="6 4"
      />

      {/* Upload arrow */}
      <path
        d="M100 130 L100 95"
        stroke="var(--primary)"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <path
        d="M88 105 L100 90 L112 105"
        stroke="var(--primary)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Cloud outline */}
      <path
        d="M75 75 C75 65 85 58 95 60 C98 52 110 48 118 55 C128 52 135 62 130 72 C135 75 135 82 130 85 L75 85 C68 85 65 78 70 75"
        stroke="var(--muted-foreground)"
        strokeWidth="1.5"
        fill="none"
        opacity="0.4"
      />

      {/* Document icon */}
      <rect x="92" y="108" width="16" height="20" rx="2" fill="var(--primary)" opacity="0.2" />
      <line x1="96" y1="115" x2="104" y2="115" stroke="var(--primary)" strokeWidth="1" opacity="0.5" />
      <line x1="96" y1="120" x2="102" y2="120" stroke="var(--primary)" strokeWidth="1" opacity="0.4" />

      {/* Decorative elements */}
      <circle cx="45" cy="110" r="3" fill="var(--accent)" opacity="0.3" />
      <circle cx="160" cy="90" r="2" fill="var(--primary)" opacity="0.4" />
    </svg>
  );
}
