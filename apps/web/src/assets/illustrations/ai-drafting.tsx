import { type SVGProps } from "react";

export function AiDraftingIllustration(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* Background circle */}
      <circle cx="100" cy="100" r="90" fill="var(--muted)" opacity="0.3" />

      {/* AI brain core */}
      <circle
        cx="100"
        cy="85"
        r="30"
        fill="var(--card)"
        stroke="var(--primary)"
        strokeWidth="2"
      />

      {/* Neural network nodes */}
      <circle cx="85" cy="75" r="4" fill="var(--primary)" opacity="0.6" />
      <circle cx="115" cy="75" r="4" fill="var(--primary)" opacity="0.6" />
      <circle cx="100" cy="65" r="4" fill="var(--accent)" opacity="0.6" />
      <circle cx="90" cy="90" r="3" fill="var(--primary)" opacity="0.4" />
      <circle cx="110" cy="90" r="3" fill="var(--accent)" opacity="0.4" />

      {/* Neural connections */}
      <line x1="85" y1="75" x2="100" y2="65" stroke="var(--primary)" strokeWidth="1" opacity="0.3" />
      <line x1="115" y1="75" x2="100" y2="65" stroke="var(--primary)" strokeWidth="1" opacity="0.3" />
      <line x1="85" y1="75" x2="90" y2="90" stroke="var(--primary)" strokeWidth="1" opacity="0.3" />
      <line x1="115" y1="75" x2="110" y2="90" stroke="var(--primary)" strokeWidth="1" opacity="0.3" />
      <line x1="90" y1="90" x2="110" y2="90" stroke="var(--accent)" strokeWidth="1" opacity="0.3" />

      {/* Sparkle on AI */}
      <path
        d="M120 60 L123 55 L126 60 L123 65 Z"
        fill="var(--accent)"
        opacity="0.7"
      />

      {/* Generated document */}
      <rect
        x="60"
        y="125"
        width="80"
        height="55"
        rx="6"
        fill="var(--card)"
        stroke="var(--border)"
        strokeWidth="1.5"
      />

      {/* Generated text lines with typing effect */}
      <line x1="72" y1="140" x2="115" y2="140" stroke="var(--primary)" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
      <line x1="72" y1="150" x2="128" y2="150" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
      <line x1="72" y1="160" x2="120" y2="160" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
      <line x1="72" y1="170" x2="110" y2="170" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" opacity="0.2" />

      {/* Cursor blink */}
      <rect x="112" y="148" width="2" height="8" fill="var(--primary)" opacity="0.8" />

      {/* Connection from AI to document */}
      <path
        d="M100 115 Q100 120 100 125"
        stroke="var(--primary)"
        strokeWidth="1.5"
        strokeDasharray="3 3"
        opacity="0.4"
      />
    </svg>
  );
}
