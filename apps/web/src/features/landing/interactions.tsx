import {
  useState,
  useRef,
  useEffect,
  useCallback,
  type ReactNode,
  type MouseEvent,
  type CSSProperties,
} from "react";
import { cn } from "@/lib/utils";

/* ============================================================
   1. Card3D — 3D tilt effect on hover
   ============================================================ */

interface Card3DProps {
  children: ReactNode;
  className?: string;
  /** Max tilt in degrees (default 8) */
  maxTilt?: number;
  /** Perspective in px (default 1000) */
  perspective?: number;
  /** Transition speed for reset (default 0.4s) */
  resetSpeed?: string;
}

export function Card3D({
  children,
  className,
  maxTilt = 8,
  perspective = 1000,
  resetSpeed = "0.4s",
}: Card3DProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [isHovering, setIsHovering] = useState(false);
  const rafRef = useRef<number>(0);

  const handleMouseMove = useCallback(
    (e: MouseEvent<HTMLDivElement>) => {
      if (!ref.current) return;
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        const rect = ref.current!.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        setTilt({
          x: ((y - centerY) / centerY) * -maxTilt,
          y: ((x - centerX) / centerX) * maxTilt,
        });
      });
    },
    [maxTilt],
  );

  const handleMouseEnter = useCallback(() => setIsHovering(true), []);
  const handleMouseLeave = useCallback(() => {
    setIsHovering(false);
    setTilt({ x: 0, y: 0 });
  }, []);

  useEffect(() => {
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  const style: CSSProperties = {
    transform: `perspective(${perspective}px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
    transition: isHovering
      ? "transform 0.1s ease-out"
      : `transform ${resetSpeed} ease-out`,
    transformStyle: "preserve-3d",
  };

  return (
    <div
      ref={ref}
      className={cn("relative", className)}
      style={style}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
    </div>
  );
}

/* ============================================================
   2. GlowEffect — Mouse-following radial glow
   ============================================================ */

interface GlowEffectProps {
  children: ReactNode;
  className?: string;
  /** Glow color (default uses primary oklch) */
  color?: string;
  /** Glow radius in px (default 300) */
  radius?: number;
  /** Glow opacity (default 0.15) */
  opacity?: number;
}

export function GlowEffect({
  children,
  className,
  color = "oklch(0.45 0.18 255)",
  radius = 300,
  opacity = 0.15,
}: GlowEffectProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isVisible, setIsVisible] = useState(false);
  const rafRef = useRef<number>(0);

  const handleMouseMove = useCallback(
    (e: MouseEvent<HTMLDivElement>) => {
      if (!containerRef.current) return;
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        const rect = containerRef.current!.getBoundingClientRect();
        setPosition({
          x: e.clientX - rect.left,
          y: e.clientY - rect.top,
        });
      });
    },
    [],
  );

  useEffect(() => {
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  return (
    <div
      ref={containerRef}
      className={cn("relative overflow-hidden", className)}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
    >
      {/* Glow overlay */}
      <div
        className="pointer-events-none absolute inset-0 z-10 transition-opacity duration-300"
        style={{
          opacity: isVisible ? opacity : 0,
          background: `radial-gradient(${radius}px circle at ${position.x}px ${position.y}px, ${color}, transparent 70%)`,
        }}
      />
      {/* Content */}
      <div className="relative z-20">{children}</div>
    </div>
  );
}

/* ============================================================
   3. RippleButton — Button with click ripple effect
   ============================================================ */

interface Ripple {
  id: number;
  x: number;
  y: number;
  size: number;
}

interface RippleButtonProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  /** Ripple color (default white with alpha) */
  rippleColor?: string;
  /** Disable ripple (for reduced-motion users) */
  disableRipple?: boolean;
}

export function RippleButton({
  children,
  className,
  onClick,
  rippleColor = "rgba(255, 255, 255, 0.35)",
  disableRipple = false,
  ...props
}: RippleButtonProps & Record<string, unknown>) {
  const [ripples, setRipples] = useState<Ripple[]>([]);
  const nextIdRef = useRef(0);

  const prefersReducedMotion =
    typeof window !== "undefined"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false;

  const shouldRipple = !disableRipple && !prefersReducedMotion;

  const handleClick = useCallback(
    (e: MouseEvent<HTMLButtonElement>) => {
      if (shouldRipple) {
        const rect = e.currentTarget.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height) * 2;
        const x = e.clientX - rect.left - size / 2;
        const y = e.clientY - rect.top - size / 2;
        const id = nextIdRef.current++;

        setRipples((prev) => [...prev, { id, x, y, size }]);

        // Remove ripple after animation
        setTimeout(() => {
          setRipples((prev) => prev.filter((r) => r.id !== id));
        }, 600);
      }
      onClick?.();
    },
    [onClick, shouldRipple],
  );

  return (
    <button
      className={cn(
        "relative overflow-hidden transition-all duration-200",
        className,
      )}
      onClick={handleClick}
      {...props}
    >
      {children}
      {ripples.map((ripple) => (
        <span
          key={ripple.id}
          className="pointer-events-none absolute animate-ripple rounded-full"
          style={{
            left: ripple.x,
            top: ripple.y,
            width: ripple.size,
            height: ripple.size,
            backgroundColor: rippleColor,
          }}
        />
      ))}
    </button>
  );
}

/* ============================================================
   4. AnimatedCounter — Number count-up animation
   ============================================================ */

interface AnimatedCounterProps {
  /** Target number */
  value: number;
  /** Animation duration in ms (default 1500) */
  duration?: number;
  /** Number of decimal places (default 0) */
  decimals?: number;
  /** Prefix (e.g. "$") */
  prefix?: string;
  /** Suffix (e.g. "%", "+") */
  suffix?: string;
  /** CSS class */
  className?: string;
  /** Whether to start animation (default true, triggers on mount / viewport entry) */
  start?: boolean;
}

export function AnimatedCounter({
  value,
  duration = 1500,
  decimals = 0,
  prefix = "",
  suffix = "",
  className,
  start = true,
}: AnimatedCounterProps) {
  const [display, setDisplay] = useState(0);
  const startTimeRef = useRef<number | null>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (!start) return;

    const prefersReducedMotion =
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (prefersReducedMotion) {
      setDisplay(value);
      return;
    }

    startTimeRef.current = null;

    const animate = (timestamp: number) => {
      if (startTimeRef.current === null) {
        startTimeRef.current = timestamp;
      }
      const elapsed = timestamp - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);

      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(eased * value);

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      } else {
        setDisplay(value);
      }
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => cancelAnimationFrame(rafRef.current);
  }, [value, duration, start]);

  const formatted = display.toFixed(decimals);
  // Add thousand separators
  const parts = formatted.split(".");
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const displayString = parts.join(".");

  return (
    <span className={className} aria-label={`${prefix}${value}${suffix}`}>
      {prefix}
      {displayString}
      {suffix}
    </span>
  );
}

/* ============================================================
   5. ScrollReveal — Intersection observer-based reveal animation
   ============================================================ */

type AnimationType =
  | "fade-up"
  | "fade-down"
  | "fade-left"
  | "fade-right"
  | "scale"
  | "blur";

interface ScrollRevealProps {
  children: ReactNode;
  className?: string;
  /** Animation type (default "fade-up") */
  animation?: AnimationType;
  /** Delay in ms for stagger effect (default 0) */
  delay?: number;
  /** Duration in ms (default 600) */
  duration?: number;
  /** Threshold for intersection (default 0.15) */
  threshold?: number;
  /** Trigger only once (default true) */
  once?: boolean;
}

const animationStyles: Record<AnimationType, { from: CSSProperties; to: CSSProperties }> = {
  "fade-up": {
    from: { opacity: 0, transform: "translateY(24px)" },
    to: { opacity: 1, transform: "translateY(0)" },
  },
  "fade-down": {
    from: { opacity: 0, transform: "translateY(-24px)" },
    to: { opacity: 1, transform: "translateY(0)" },
  },
  "fade-left": {
    from: { opacity: 0, transform: "translateX(24px)" },
    to: { opacity: 1, transform: "translateX(0)" },
  },
  "fade-right": {
    from: { opacity: 0, transform: "translateX(-24px)" },
    to: { opacity: 1, transform: "translateX(0)" },
  },
  scale: {
    from: { opacity: 0, transform: "scale(0.92)" },
    to: { opacity: 1, transform: "scale(1)" },
  },
  blur: {
    from: { opacity: 0, filter: "blur(8px)" },
    to: { opacity: 1, filter: "blur(0)" },
  },
};

export function ScrollReveal({
  children,
  className,
  animation = "fade-up",
  delay = 0,
  duration = 600,
  threshold = 0.15,
  once = true,
}: ScrollRevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    if (prefersReducedMotion) {
      setIsVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          if (once) observer.unobserve(el);
        } else if (!once) {
          setIsVisible(false);
        }
      },
      { threshold },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold, once]);

  const { from, to } = animationStyles[animation];
  const currentStyle = isVisible ? to : from;

  return (
    <div
      ref={ref}
      className={className}
      style={{
        ...currentStyle,
        transition: `opacity ${duration}ms ease-out ${delay}ms, transform ${duration}ms ease-out ${delay}ms, filter ${duration}ms ease-out ${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}

/* ============================================================
   6. MagneticButton — Button that subtly follows cursor
   ============================================================ */

interface MagneticButtonProps {
  children: ReactNode;
  className?: string;
  /** Strength of magnetic pull (default 0.3) */
  strength?: number;
  onClick?: () => void;
}

export function MagneticButton({
  children,
  className,
  strength = 0.3,
  onClick,
}: MagneticButtonProps) {
  const ref = useRef<HTMLButtonElement>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const rafRef = useRef<number>(0);

  const handleMouseMove = useCallback(
    (e: MouseEvent<HTMLButtonElement>) => {
      if (!ref.current) return;
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        const rect = ref.current!.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        setOffset({
          x: (e.clientX - centerX) * strength,
          y: (e.clientY - centerY) * strength,
        });
      });
    },
    [strength],
  );

  const handleMouseLeave = useCallback(() => {
    setOffset({ x: 0, y: 0 });
  }, []);

  useEffect(() => {
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  return (
    <button
      ref={ref}
      className={cn("transition-transform duration-200 ease-out", className)}
      style={{
        transform: `translate(${offset.x}px, ${offset.y}px)`,
      }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
