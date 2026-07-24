import type { ReactNode, HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/** Static shell: scroll-driven entrance choreography removed. */
export type AnimatedContentProps = {
  children?: ReactNode;
  distance?: number;
  direction?: "vertical" | "horizontal";
  reverse?: boolean;
  duration?: number;
  ease?: string;
  initialOpacity?: number;
  animateOpacity?: boolean;
  scale?: number;
  threshold?: number;
  delay?: number;
  className?: string;
} & HTMLAttributes<HTMLDivElement>;

export default function AnimatedContent({
  children,
  className,
  ...props
}: AnimatedContentProps) {
  return (
    <div className={cn(className)} {...props}>
      {children}
    </div>
  );
}
