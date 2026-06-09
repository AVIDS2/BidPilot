import { type SVGProps } from "react";

export function GenerateIllustration(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* Background circle */}
      <circle cx="100" cy="100" r="90" fill="var(--muted)" opacity="0.3" />

      {/* AI core */}
      <circle
        cx="100"
        cy="85"
        r="25"
        fill="var(--card)"
        stroke="var(--primary)"
        strokeWidth="2"
      />

      {/* Brain pattern */}
      <path
        d="M90 80 C90 75 95 72 100 75 C105 72 110 75 110 80"
        stroke="var(--primary)"
        strokeWidth="1.5"
        fill="none"
        opacity="0.6"
      />
      <circle cx="95" cy="82" r="2" fill="var(--primary)" opacity="0.5" />
      <circle cx="105" cy="82" r="2" fill="var(--primary)" opacity="0.5" />

      {/* Processing lines */}
      <path
        d="M75 95 Q100 100 125 95"
        stroke="var(--accent)"
        strokeWidth="1.5"
        strokeDasharray="4 4"
        opacity="0.4"
      />

      {/* Generated content */}
      <rect
        x="60"
        y="120"
        width="80"
        height="50"
        rx="6"
        fill="var(--card)"
        stroke="var(--border)"
        strokeWidth="1.5"
      />

      {/* Content lines */}
      <line x1="72" y1="135" x2="120" y2="135" stroke="var(--primary)" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
      <line x1="72" y1="145" x2="128" y2="145" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
      <line x1="72" y1="155" x2="115" y2="155" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />

      {/* Connection */}
      <path
        d="M100 110 L100 120"
        stroke="var(--primary)"
        strokeWidth="1.5"
        strokeDasharray="3 3"
        opacity="0.4"
      />

      {/* Sparkles */}
      <path
        d="M130 70 L133 65 L136 70 L133 75 Z"
        fill="var(--accent)"
        opacity="0.6"
      />
      <path
        d="M70 65 L72 61 L74 65 L72 69 Z"
        fill="var(--primary)"
        opacity="0.5"
      />
    </svg>
  );
}
