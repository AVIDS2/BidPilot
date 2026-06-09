import { type SVGProps } from "react";

export function ReviewExportIllustration(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* Background circle */}
      <circle cx="100" cy="100" r="90" fill="var(--muted)" opacity="0.3" />

      {/* Document */}
      <rect
        x="55"
        y="45"
        width="70"
        height="85"
        rx="6"
        fill="var(--card)"
        stroke="var(--border)"
        strokeWidth="1.5"
      />

      {/* Document lines */}
      <line x1="68" y1="62" x2="110" y2="62" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
      <line x1="68" y1="72" x2="105" y2="72" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
      <line x1="68" y1="82" x2="112" y2="82" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
      <line x1="68" y1="92" x2="100" y2="92" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />

      {/* Approval stamp */}
      <circle cx="140" cy="70" r="15" fill="var(--primary)" opacity="0.1" />
      <path
        d="M132 70 L137 75 L148 64"
        stroke="var(--primary)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Export arrow */}
      <path
        d="M100 135 L100 160"
        stroke="var(--primary)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M92 152 L100 162 L108 152"
        stroke="var(--primary)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Export format icons */}
      <rect x="70" y="165" width="20" height="16" rx="3" fill="var(--primary)" opacity="0.15" />
      <text x="80" y="177" textAnchor="middle" fill="var(--primary)" fontSize="8" fontWeight="600" opacity="0.6">PDF</text>

      <rect x="95" y="165" width="20" height="16" rx="3" fill="var(--accent)" opacity="0.15" />
      <text x="105" y="177" textAnchor="middle" fill="var(--accent)" fontSize="8" fontWeight="600" opacity="0.6">DOC</text>

      <rect x="120" y="165" width="20" height="16" rx="3" fill="var(--primary)" opacity="0.15" />
      <text x="130" y="177" textAnchor="middle" fill="var(--primary)" fontSize="8" fontWeight="600" opacity="0.6">XLS</text>

      {/* Decorative */}
      <circle cx="45" cy="85" r="2.5" fill="var(--accent)" opacity="0.3" />
      <circle cx="160" cy="100" r="3" fill="var(--primary)" opacity="0.3" />
    </svg>
  );
}
