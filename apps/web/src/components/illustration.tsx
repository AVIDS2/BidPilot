import { type ReactNode, type SVGProps } from "react";
import { cn } from "@/lib/utils";

// Size presets
const sizePresets = {
  sm: "size-12",
  md: "size-16",
  lg: "size-24",
  xl: "size-32",
  "2xl": "size-48",
  full: "w-full h-auto",
} as const;

type IllustrationSize = keyof typeof sizePresets;

interface IllustrationProps extends SVGProps<SVGSVGElement> {
  /** Illustration component to render */
  illustration: (props: SVGProps<SVGSVGElement>) => ReactNode;
  /** Size preset or custom className */
  size?: IllustrationSize;
  /** Additional className */
  className?: string;
}

/**
 * Unified wrapper for illustrations with consistent sizing and styling.
 *
 * @example
 * ```tsx
 * import { Illustration } from "@/components/illustration";
 * import { RfpParsingIllustration } from "@/assets/illustrations";
 *
 * <Illustration illustration={RfpParsingIllustration} size="xl" />
 * ```
 */
export function Illustration({
  illustration: IllustrationComponent,
  size = "lg",
  className,
  ...props
}: IllustrationProps) {
  return (
    <IllustrationComponent
      className={cn(sizePresets[size], className)}
      {...props}
    />
  );
}

interface StatsIconProps extends SVGProps<SVGSVGElement> {
  /** Icon component to render */
  icon: (props: SVGProps<SVGSVGElement>) => ReactNode;
  /** Size in pixels */
  size?: number;
  /** Additional className */
  className?: string;
}

/**
 * Wrapper for stats icons with consistent sizing.
 *
 * @example
 * ```tsx
 * import { StatsIcon } from "@/components/illustration";
 * import { DocumentStatsIcon } from "@/assets/illustrations";
 *
 * <StatsIcon icon={DocumentStatsIcon} size={24} />
 * ```
 */
export function StatsIcon({
  icon: IconComponent,
  size = 24,
  className,
  ...props
}: StatsIconProps) {
  return (
    <IconComponent
      style={{ width: size, height: size }}
      className={cn("shrink-0", className)}
      {...props}
    />
  );
}
