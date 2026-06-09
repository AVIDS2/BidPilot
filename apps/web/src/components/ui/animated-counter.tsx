import * as React from "react";
import { useScrollAnimation } from "@/hooks/use-scroll-animation";

interface AnimatedCounterProps {
  /** Target number to count to */
  target: number;
  /** Duration of the counting animation in ms. Default: 2000 */
  duration?: number;
  /** Number of decimal places. Default: 0 */
  decimals?: number;
  /** Prefix string (e.g., "$") */
  prefix?: string;
  /** Suffix string (e.g., "%", "+") */
  suffix?: string;
  /** Locale for number formatting. Default: "en-US" */
  locale?: string;
  /** Additional className */
  className?: string;
}

export function AnimatedCounter({
  target,
  duration = 2000,
  decimals = 0,
  prefix = "",
  suffix = "",
  locale = "en-US",
  className,
}: AnimatedCounterProps) {
  const { ref, isVisible } = useScrollAnimation({ threshold: 0.3 });
  const [current, setCurrent] = React.useState(0);
  const frameRef = React.useRef<number>(0);

  React.useEffect(() => {
    if (!isVisible) return;

    const startTime = performance.now();
    const startValue = 0;

    const easeOutQuart = (t: number) => 1 - Math.pow(1 - t, 4);

    const animate = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easedProgress = easeOutQuart(progress);

      setCurrent(startValue + (target - startValue) * easedProgress);

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      }
    };

    frameRef.current = requestAnimationFrame(animate);

    return () => cancelAnimationFrame(frameRef.current);
  }, [isVisible, target, duration]);

  const formatted = new Intl.NumberFormat(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(current);

  return (
    <span ref={ref as React.RefObject<HTMLSpanElement>} className={className}>
      {prefix}
      {formatted}
      {suffix}
    </span>
  );
}
