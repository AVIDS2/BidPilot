import { useState } from "react";
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

  const showParticles = variant === "particles" || variant === "mixed";
  const showGrid = variant === "grid" || variant === "mixed";

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
      {showParticles && (
        <div
          className="absolute inset-0"
          style={{ mixBlendMode: "screen", zIndex: 4 }}
        >
          <AnimeParticles
            color="#84cc16"
            count={variant === "mixed" ? 25 : 40}
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

      {/* 层7: 影视画框标注 */}
      <FieldGuide />

      {/* 层8: 内容 */}
      <div className="relative z-20 flex flex-col justify-center h-full px-8 max-w-7xl mx-auto">
        {children}
      </div>
    </div>
  );
}

// 影视画框叠加组件
function FieldGuide() {
  return (
    <div className="absolute inset-0 pointer-events-none z-10">
      <span className="absolute top-6 left-6 text-[10px] text-white/30 font-mono">
        BidPilot v1.0
      </span>
      <span className="absolute top-6 right-6 text-[10px] text-white/30 font-mono">
        [16:9]
      </span>
      <span className="absolute bottom-6 left-6 text-[10px] text-white/30 font-mono">
        OVERSCAN: 1920 x 1080
      </span>
      <span className="absolute bottom-6 right-6 text-[10px] text-white/30 font-mono">
        100%
      </span>

      {/* 十字准星 */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
        <div className="w-8 h-px bg-white/20" />
        <div className="w-px h-8 bg-white/20 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
      </div>

      {/* 边框线 */}
      <div className="absolute inset-8 border border-white/5" />
      <div className="absolute inset-16 border border-white/3" />
    </div>
  );
}
