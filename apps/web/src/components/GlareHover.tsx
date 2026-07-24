import type { ReactNode, HTMLAttributes, CSSProperties } from "react";
import { cn } from "@/lib/utils";

/** No-op shell: glare sweep removed. */
export type GlareHoverProps = {
  children?: ReactNode;
  width?: string;
  height?: string;
  background?: string;
  borderRadius?: string;
  borderColor?: string;
  glareColor?: string;
  glareOpacity?: number;
  glareSize?: number;
  transitionDuration?: number;
  playOnce?: boolean;
  className?: string;
  style?: CSSProperties;
} & HTMLAttributes<HTMLDivElement>;

export default function GlareHover({
  children,
  className,
  style,
  width,
  height,
  ...props
}: GlareHoverProps) {
  return (
    <div className={cn(className)} style={{ width, height, ...style }} {...props}>
      {children}
    </div>
  );
}
