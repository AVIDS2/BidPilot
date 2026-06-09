import * as React from "react";
import { cn } from "@/lib/utils";

interface ScrollProgressProps {
  /** Additional className for the outer container */
  className?: string;
  /** Height of the progress bar. Default: "3px" */
  height?: string;
}

export function ScrollProgress({
  className,
  height = "3px",
}: ScrollProgressProps) {
  const [progress, setProgress] = React.useState(0);

  React.useEffect(() => {
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    let ticking = false;

    const updateProgress = () => {
      const scrollTop = window.scrollY;
      const docHeight =
        document.documentElement.scrollHeight - window.innerHeight;
      const scrollPercent = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
      setProgress(scrollPercent);
      ticking = false;
    };

    const onScroll = () => {
      if (!ticking) {
        if (prefersReducedMotion) {
          // No rAF for reduced motion — update directly
          updateProgress();
        } else {
          requestAnimationFrame(updateProgress);
        }
        ticking = true;
      }
    };

    updateProgress();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      className={cn(
        "fixed top-0 left-0 z-50 w-full",
        className,
      )}
      style={{ height }}
      role="progressbar"
      aria-valuenow={Math.round(progress)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Page scroll progress"
    >
      <div
        className="h-full transition-[width] duration-150 ease-out"
        style={{
          width: `${progress}%`,
          background:
            "linear-gradient(90deg, var(--primary), var(--accent))",
        }}
      />
    </div>
  );
}
