import { type SVGProps } from "react";

export function QualityReviewIllustration(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* Background circle */}
      <circle cx="100" cy="100" r="90" fill="var(--muted)" opacity="0.3" />

      {/* Document base */}
      <rect
        x="55"
        y="35"
        width="75"
        height="95"
        rx="6"
        fill="var(--card)"
        stroke="var(--border)"
        strokeWidth="1.5"
      />

      {/* Document lines */}
      <line x1="70" y1="55" x2="115" y2="55" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
      <line x1="70" y1="65" x2="110" y2="65" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
      <line x1="70" y1="75" x2="118" y2="75" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
      <line x1="70" y1="85" x2="105" y2="85" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
      <line x1="70" y1="95" x2="112" y2="95" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
      <line x1="70" y1="105" x2="100" y2="105" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />

      {/* Check marks */}
      <circle cx="140" cy="55" r="8" fill="var(--primary)" opacity="0.15" />
      <path
        d="M136 55 L139 58 L145 52"
        stroke="var(--primary)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      <circle cx="140" cy="75" r="8" fill="var(--primary)" opacity="0.15" />
      <path
        d="M136 75 L139 78 L145 72"
        stroke="var(--primary)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      <circle cx="140" cy="95" r="8" fill="var(--primary)" opacity="0.15" />
      <path
        d="M136 95 L139 98 L145 92"
        stroke="var(--primary)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Quality score badge */}
      <rect
        x="75"
        y="145"
        width="50"
        height="30"
        rx="15"
        fill="var(--primary)"
        opacity="0.15"
      />
      <text
        x="100"
        y="165"
        textAnchor="middle"
        fill="var(--primary)"
        fontSize="14"
        fontWeight="600"
      >
        A+
      </text>

      {/* Shield icon */}
      <path
        d="M100 140 L100 150"
        stroke="var(--primary)"
        strokeWidth="1.5"
        opacity="0.4"
      />

      {/* Decorative dots */}
      <circle cx="45" cy="80" r="3" fill="var(--accent)" opacity="0.3" />
      <circle cx="160" cy="60" r="2" fill="var(--accent)" opacity="0.4" />
      <circle cx="155" cy="130" r="2.5" fill="var(--primary)" opacity="0.3" />
    </svg>
  );
}
