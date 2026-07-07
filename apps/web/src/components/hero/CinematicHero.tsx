import { useEffect, useState } from "react";
import { AnimeParticles } from "./AnimeParticles";
import { TechGrid } from "./TechGrid";

interface CinematicHeroProps {
  variant?: "particles" | "grid" | "mixed";
  videoSrc?: string;
  posterSrc?: string;
  children?: React.ReactNode;
}

export function CinematicHero({
  variant = "mixed",
  videoSrc,
  posterSrc,
  children,
}: CinematicHeroProps) {
  const [videoReady, setVideoReady] = useState(false);
  const [effectsReady, setEffectsReady] = useState(false);

  const showParticles = variant === "particles" || variant === "mixed";
  const showGrid = variant === "grid" || variant === "mixed";

  useEffect(() => {
    const win = window as Window & {
      requestIdleCallback?: (callback: () => void) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    const id = win.requestIdleCallback
      ? win.requestIdleCallback(() => setEffectsReady(true))
      : window.setTimeout(() => setEffectsReady(true), 180);
    return () => {
      if (win.cancelIdleCallback) {
        win.cancelIdleCallback(id);
      } else {
        window.clearTimeout(id);
      }
    };
  }, []);

  return (
    <div className="relative min-h-[100dvh] overflow-hidden">
      {/* 层1: 纯黑底色（兜底） */}
      <div className="absolute inset-0 bg-[#0a0a0a]" />

      {/* 层2: 视频背景（如果有） */}
      {videoSrc && (
        <video
          autoPlay
          muted
          loop
          playsInline
          poster={posterSrc}
          onLoadedData={() => setVideoReady(true)}
          className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-[2000ms] ${
            videoReady ? "opacity-40" : "opacity-0"
          }`}
          style={{ zIndex: 1 }}
        >
          <source src={videoSrc} type="video/mp4" />
        </video>
      )}

      {/* 层3: 暗色蒙版（压住视频亮度，保持电影调性） */}
      {videoSrc && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "linear-gradient(to bottom, rgba(10,10,10,0.5), rgba(10,10,10,0.8))",
            zIndex: 2,
          }}
        />
      )}

      {/* 层4: 网格（screen 混合，浮在视频上自然发光） */}
      {showGrid && (
        <div
          className="absolute inset-0"
          style={{ mixBlendMode: "screen", zIndex: 3 }}
        >
          <TechGrid
            color="#84cc16"
            opacity={variant === "mixed" ? 0.06 : 0.08}
            cellSize={variant === "mixed" ? 80 : 60}
            animated={false}
          />
        </div>
      )}

      {/* 层5: 粒子（screen 混合） */}
      {showParticles && effectsReady && (
        <div
          className="absolute inset-0"
          style={{ mixBlendMode: "screen", zIndex: 4 }}
        >
          <AnimeParticles
            color="#84cc16"
            count={variant === "mixed" ? 18 : 28}
            speed={variant === "mixed" ? 0.6 : 0.8}
            size={variant === "mixed" ? 2 : 3}
          />
        </div>
      )}

      {/* 层6: 底部渐变过渡 */}
      <div
        className="absolute bottom-0 left-0 right-0 h-48 pointer-events-none"
        style={{
          background: "linear-gradient(to bottom, transparent, #0a0a0a)",
          zIndex: 15,
        }}
      />

      {/* 层7: 极简角标（仅保留品牌标识，去掉技术参数） */}
      <MinimalGuide />

      {/* 层8: 内容 */}
      <div className="relative z-20 mx-auto flex min-h-[100dvh] w-full max-w-7xl flex-col justify-center px-5 py-28 sm:px-8 sm:py-32">
        {children}
      </div>
    </div>
  );
}

// 极简角标 — 只保留品牌定位，去掉开发者技术参数
function MinimalGuide() {
  return (
    <div className="absolute inset-0 pointer-events-none z-10">
      {/* 左上角：品牌标识 */}
      <span className="absolute top-5 left-5 text-[10px] text-white/20 font-mono tracking-widest uppercase sm:top-6 sm:left-6">
        BidPilot
      </span>

      {/* 右上角：行业定位 */}
      <span className="absolute top-5 right-5 text-[10px] text-white/20 font-mono tracking-widest uppercase sm:top-6 sm:right-6">
        Bid Intelligence
      </span>

      {/* 极淡的边框线 — 仅在大屏显示，增加电影感 */}
      <div className="hidden sm:block absolute inset-x-8 inset-y-20 border border-white/[0.03]" />
    </div>
  );
}
