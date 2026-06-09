import * as React from "react";

interface ParallaxOptions {
  /** Parallax speed multiplier (0 = static, 0.5 = half speed, 1 = full scroll speed). Default: 0.3 */
  speed?: number;
  /** Enable/disable. Default: true */
  enabled?: boolean;
  /** Direction: vertical or horizontal. Default: "vertical" */
  direction?: "vertical" | "horizontal";
}

export function useParallax(options: ParallaxOptions = {}) {
  const { speed = 0.3, enabled = true, direction = "vertical" } = options;
  const ref = React.useRef<HTMLElement>(null);
  const [offset, setOffset] = React.useState(0);

  React.useEffect(() => {
    if (!enabled) return;

    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (prefersReducedMotion) return;

    const el = ref.current;
    if (!el) return;

    let ticking = false;

    const updateOffset = () => {
      const rect = el.getBoundingClientRect();
      const windowHeight = window.innerHeight;
      const windowWidth = window.innerWidth;

      // Element center relative to viewport center
      const elementCenter =
        direction === "vertical"
          ? rect.top + rect.height / 2
          : rect.left + rect.width / 2;
      const viewportCenter =
        direction === "vertical" ? windowHeight / 2 : windowWidth / 2;

      // Normalized distance: -1 (above) to +1 (below)
      const normalizedDistance =
        (elementCenter - viewportCenter) / viewportCenter;

      setOffset(normalizedDistance * speed * 100);
      ticking = false;
    };

    const onScroll = () => {
      if (!ticking) {
        requestAnimationFrame(updateOffset);
        ticking = true;
      }
    };

    updateOffset();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });

    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [speed, enabled, direction]);

  const style: React.CSSProperties = {
    transform:
      direction === "vertical"
        ? `translateY(${offset}px)`
        : `translateX(${offset}px)`,
    willChange: "transform",
  };

  return { ref, offset, style };
}
