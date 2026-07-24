import type { ReactNode, HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/** No-op shell: click particle sparks removed. */
export type ClickSparkProps = {
  children?: ReactNode;
  sparkColor?: string;
  sparkSize?: number;
  sparkRadius?: number;
  sparkCount?: number;
  duration?: number;
  easing?: string;
  extraScale?: number;
  className?: string;
} & HTMLAttributes<HTMLDivElement>;

export default function ClickSpark({
  children,
  className,
  ...props
}: ClickSparkProps) {
  return (
    <div className={cn(className)} {...props}>
      {children}
    </div>
  );
}
