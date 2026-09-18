import { useState } from "react";
import { cn } from "@/lib/utils";

type InteractiveGridPatternProps = React.SVGProps<SVGSVGElement> & {
  width?: number;
  height?: number;
  squares?: [number, number];
  squaresClassName?: string;
};

/**
 * Adapted from Kiranism/next-shadcn-dashboard-starter's MIT-licensed
 * InteractiveGridPattern component. It remains decorative and does not carry
 * product state or authentication behavior.
 */
export function InteractiveGridPattern({
  width = 40,
  height = 40,
  squares = [24, 24],
  className,
  squaresClassName,
  ...props
}: InteractiveGridPatternProps) {
  const [horizontal, vertical] = squares;
  const [hoveredSquare, setHoveredSquare] = useState<number | null>(null);

  return (
    <svg
      aria-hidden="true"
      width={width * horizontal}
      height={height * vertical}
      className={cn(
        "absolute inset-0 h-full w-full border border-sidebar-border/40",
        className,
      )}
      {...props}
    >
      {Array.from({ length: horizontal * vertical }).map((_, index) => {
        const x = (index % horizontal) * width;
        const y = Math.floor(index / horizontal) * height;
        return (
          <rect
            key={index}
            x={x}
            y={y}
            width={width}
            height={height}
            className={cn(
              "stroke-sidebar-border/40 transition-all duration-100 ease-in-out [&:not(:hover)]:duration-1000",
              hoveredSquare === index ? "fill-sidebar-accent/70" : "fill-transparent",
              squaresClassName,
            )}
            onMouseEnter={() => setHoveredSquare(index)}
            onMouseLeave={() => setHoveredSquare(null)}
          />
        );
      })}
    </svg>
  );
}
