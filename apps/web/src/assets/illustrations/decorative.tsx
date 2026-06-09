import { type SVGProps } from "react";

/** 渐变光晕 - 用于背景装饰 */
export function GradientGlow(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 400 400" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <defs>
        <radialGradient id="glow1" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="glow2" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.2" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="200" cy="200" r="150" fill="url(#glow1)" className="hero-glow-pulse" />
      <circle cx="250" cy="180" r="100" fill="url(#glow2)" className="hero-glow-pulse" style={{ animationDelay: "2s" }} />
    </svg>
  );
}

/** 网格纹理 - 用于背景装饰 */
export function GridTexture(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <defs>
        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <circle cx="10" cy="10" r="1" fill="var(--muted-foreground)" opacity="0.15" />
        </pattern>
      </defs>
      <rect width="100" height="100" fill="url(#grid)" />
    </svg>
  );
}

/** 浮动形状 - 用于动态装饰 */
export function FloatingShapes(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      {/* Circle */}
      <circle
        cx="60"
        cy="80"
        r="15"
        fill="var(--primary)"
        opacity="0.1"
        className="hero-float-1"
      />

      {/* Square */}
      <rect
        x="130"
        y="60"
        width="25"
        height="25"
        rx="4"
        fill="var(--accent)"
        opacity="0.1"
        className="hero-float-2"
      />

      {/* Triangle */}
      <path
        d="M100 140 L115 165 L85 165 Z"
        fill="var(--primary)"
        opacity="0.08"
        className="hero-float-3"
      />

      {/* Small dots */}
      <circle cx="40" cy="50" r="3" fill="var(--primary)" opacity="0.15" className="hero-float-2" />
      <circle cx="170" cy="120" r="4" fill="var(--accent)" opacity="0.12" className="hero-float-1" />
      <circle cx="80" cy="170" r="2.5" fill="var(--primary)" opacity="0.1" className="hero-float-3" />
    </svg>
  );
}

/** 连接线条 - 用于流程装饰 */
export function ConnectingLines(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 600 100" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <defs>
        <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0" />
          <stop offset="20%" stopColor="var(--primary)" stopOpacity="0.3" />
          <stop offset="80%" stopColor="var(--accent)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Main connecting line */}
      <path
        d="M0 50 Q150 30 300 50 Q450 70 600 50"
        stroke="url(#lineGrad)"
        strokeWidth="1.5"
        fill="none"
      />

      {/* Connection points */}
      <circle cx="100" cy="42" r="4" fill="var(--primary)" opacity="0.4" />
      <circle cx="300" cy="50" r="5" fill="var(--primary)" opacity="0.5" />
      <circle cx="500" cy="42" r="4" fill="var(--accent)" opacity="0.4" />

      {/* Dotted branches */}
      <line x1="100" y1="42" x2="100" y2="80" stroke="var(--primary)" strokeWidth="1" strokeDasharray="3 3" opacity="0.2" />
      <line x1="300" y1="50" x2="300" y2="85" stroke="var(--primary)" strokeWidth="1" strokeDasharray="3 3" opacity="0.2" />
      <line x1="500" y1="42" x2="500" y2="80" stroke="var(--accent)" strokeWidth="1" strokeDasharray="3 3" opacity="0.2" />
    </svg>
  );
}
