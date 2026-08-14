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
  background,
  borderRadius,
  borderColor,
  glareColor: _glareColor,
  glareOpacity: _glareOpacity,
  glareSize: _glareSize,
  transitionDuration: _transitionDuration,
  playOnce: _playOnce,
  ...htmlProps
}: GlareHoverProps) {
  return (
    <div
      className={cn(className)}
      style={{
        width,
        height,
        background,
        borderRadius,
        borderColor,
        ...style,
      }}
      {...htmlProps}
    >
      {children}
    </div>
  );
}
