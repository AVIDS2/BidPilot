/** Quiet product accent tokens (no purple/violet aurora). */
export const REACTBITS_AURORA = {
  accent: "var(--primary)",
  accentAlt: "var(--ring)",
  accentHot: "var(--primary)",
  border: "color-mix(in oklch, var(--border) 80%, transparent)",
  borderStrong: "color-mix(in oklch, var(--ring) 45%, transparent)",
  glow: "transparent",
  star: "var(--primary)",
  gradient: "var(--primary)",
  softGradient: "color-mix(in oklch, var(--muted) 80%, transparent)",
} as const;
