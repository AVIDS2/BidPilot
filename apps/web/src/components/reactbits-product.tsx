import type { ReactNode } from "react";
import ElectricBorder from "@/components/ElectricBorder";
import FadeContent from "@/components/FadeContent";
import GlareHover from "@/components/GlareHover";
import ShinyText from "@/components/ShinyText";
import { REACTBITS_AURORA } from "@/components/reactbits-theme";
import { usePrefersReducedMotion } from "@/hooks/use-prefers-reduced-motion";
import { cn } from "@/lib/utils";

export function ProductReveal({
  children,
  className,
  delay = 0,
  blur = true,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  blur?: boolean;
}) {
  const prefersReducedMotion = usePrefersReducedMotion();

  if (prefersReducedMotion) {
    return <div className={className}>{children}</div>;
  }

  return (
    <FadeContent blur={blur} duration={420} delay={delay} threshold={0.04} className={className}>
      {children}
    </FadeContent>
  );
}

export function ProductGlareCard({
  children,
  className,
  intense = false,
}: {
  children: ReactNode;
  className?: string;
  intense?: boolean;
}) {
  const prefersReducedMotion = usePrefersReducedMotion();

  if (prefersReducedMotion) {
    return <div className={cn("min-w-0", className)}>{children}</div>;
  }

  return (
    <GlareHover
      width="100%"
      height="100%"
      background="transparent"
      borderColor="transparent"
      borderRadius="1rem"
      glareColor={REACTBITS_AURORA.accentAlt}
      glareOpacity={intense ? 0.22 : 0.13}
      glareSize={180}
      transitionDuration={720}
      className={cn("!block !overflow-visible h-full min-w-0 cursor-default border-0 bg-transparent", className)}
    >
      {children}
    </GlareHover>
  );
}

export function ProductElectricFrame({
  children,
  className,
  active = true,
  radius = 18,
}: {
  children: ReactNode;
  className?: string;
  active?: boolean;
  radius?: number;
}) {
  const prefersReducedMotion = usePrefersReducedMotion();

  if (!active || prefersReducedMotion) {
    return <div className={className}>{children}</div>;
  }

  return (
    <ElectricBorder
      color={REACTBITS_AURORA.accent}
      speed={0.52}
      chaos={0.035}
      borderRadius={radius}
      className={cn("reactbits-aurora-breathe", className)}
    >
      {children}
    </ElectricBorder>
  );
}

export function ProductShinyText({
  text,
  className,
  muted = false,
}: {
  text: string;
  className?: string;
  muted?: boolean;
}) {
  const prefersReducedMotion = usePrefersReducedMotion();

  return (
    <ShinyText
      text={text}
      disabled={prefersReducedMotion}
      speed={3.1}
      color={muted ? "var(--muted-foreground)" : "var(--foreground)"}
      shineColor={REACTBITS_AURORA.accentAlt}
      spread={105}
      className={className}
    />
  );
}
