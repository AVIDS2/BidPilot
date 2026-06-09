import * as React from "react";

interface ScrollAnimationOptions {
  /** Viewport intersection threshold (0-1). Default: 0.1 */
  threshold?: number;
  /** Animation delay in ms. Default: 0 */
  delay?: number;
  /** Only trigger once. Default: true */
  once?: boolean;
  /** Root margin for IntersectionObserver */
  rootMargin?: string;
}

export function useScrollAnimation(options: ScrollAnimationOptions = {}) {
  const { threshold = 0.1, delay = 0, once = true, rootMargin } = options;
  const ref = React.useRef<HTMLElement>(null);
  const [isVisible, setIsVisible] = React.useState(false);

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    // If reduced motion, skip animation and show immediately
    if (prefersReducedMotion) {
      setIsVisible(true);
      return;
    }

    let timer: ReturnType<typeof setTimeout>;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          if (delay > 0) {
            timer = setTimeout(() => setIsVisible(true), delay);
          } else {
            setIsVisible(true);
          }
          if (once) observer.unobserve(entry.target);
        } else if (!once) {
          setIsVisible(false);
        }
      },
      { threshold, rootMargin },
    );

    observer.observe(el);

    return () => {
      observer.disconnect();
      clearTimeout(timer);
    };
  }, [threshold, delay, once, rootMargin]);

  return { ref, isVisible };
}

/**
 * Stagger-aware variant: returns a function that returns a delay for each child index.
 */
export function useStaggerAnimation(
  count: number,
  baseDelay = 80,
  options: Omit<ScrollAnimationOptions, "delay"> = {},
) {
  const { ref, isVisible } = useScrollAnimation(options);

  const getDelay = React.useCallback(
    (index: number) => (isVisible ? index * baseDelay : 0),
    [isVisible, baseDelay],
  );

  return { ref, isVisible, getDelay };
}
