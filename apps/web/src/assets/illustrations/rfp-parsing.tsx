import { type SVGProps } from "react";

export function RfpParsingIllustration(props: SVGProps<SVGSVGElement>) {
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
        y="40"
        width="70"
        height="90"
        rx="6"
        fill="var(--card)"
        stroke="var(--border)"
        strokeWidth="1.5"
      />

      {/* Document lines */}
      <line x1="70" y1="60" x2="110" y2="60" stroke="var(--muted-foreground)" strokeWidth="2" strokeLinecap="round" opacity="0.4" />
      <line x1="70" y1="72" x2="105" y2="72" stroke="var(--muted-foreground)" strokeWidth="2" strokeLinecap="round" opacity="0.3" />
      <line x1="70" y1="84" x2="112" y2="84" stroke="var(--muted-foreground)" strokeWidth="2" strokeLinecap="round" opacity="0.4" />
      <line x1="70" y1="96" x2="98" y2="96" stroke="var(--muted-foreground)" strokeWidth="2" strokeLinecap="round" opacity="0.3" />
      <line x1="70" y1="108" x2="108" y2="108" stroke="var(--muted-foreground)" strokeWidth="2" strokeLinecap="round" opacity="0.4" />

      {/* Magnifying glass */}
      <circle
        cx="130"
        cy="75"
        r="18"
        fill="var(--background)"
        stroke="var(--primary)"
        strokeWidth="2.5"
      />
      <line
        x1="143"
        y1="88"
        x2="155"
        y2="100"
        stroke="var(--primary)"
        strokeWidth="2.5"
        strokeLinecap="round"
      />

      {/* Analysis sparkle */}
      <circle cx="125" cy="65" r="3" fill="var(--primary)" opacity="0.6" />
      <circle cx="138" cy="70" r="2" fill="var(--accent)" opacity="0.5" />

      {/* Data extraction arrows */}
      <path
        d="M90 130 L90 155 L110 155"
        stroke="var(--primary)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.5"
      />
      <path
        d="M110 130 L110 155 L90 155"
        stroke="var(--accent)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.5"
      />

      {/* Extracted data blocks */}
      <rect x="65" y="158" width="20" height="12" rx="3" fill="var(--primary)" opacity="0.2" />
      <rect x="90" y="158" width="25" height="12" rx="3" fill="var(--accent)" opacity="0.2" />
      <rect x="120" y="158" width="18" height="12" rx="3" fill="var(--primary)" opacity="0.15" />
    </svg>
  );
}
