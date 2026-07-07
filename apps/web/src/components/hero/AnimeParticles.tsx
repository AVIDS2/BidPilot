import { useEffect, useRef } from "react";

interface AnimeParticlesProps {
  color?: string;
  count?: number;
  speed?: number;
  size?: number;
}

export function AnimeParticles({
  color = "#84cc16",
  count = 50,
  speed = 1,
  size = 3,
}: AnimeParticlesProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const effectiveCount = Math.min(count, window.innerWidth < 768 ? 12 : count);

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const particles: Array<{
      x: number;
      y: number;
      vx: number;
      vy: number;
      size: number;
      color: string;
      alpha: number;
      life: number;
      maxLife: number;
      fadeIn: number;
      shape: "circle" | "square" | "diamond";
    }> = [];

    const createParticle = () => {
      const shapes: Array<"circle" | "square" | "diamond"> = [
        "circle",
        "square",
        "diamond",
      ];
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * speed,
        vy: (Math.random() - 0.5) * speed,
        size: Math.random() * size + 1,
        color,
        alpha: Math.random() * 0.5 + 0.1,
        life: Math.random() * 200 + 100,
        maxLife: Math.random() * 200 + 100,
        fadeIn: 0,
        shape: shapes[Math.floor(Math.random() * shapes.length)],
      });
    };

    for (let i = 0; i < effectiveCount; i++) {
      createParticle();
    }

    const drawParticle = (p: (typeof particles)[0]) => {
      ctx.save();
      ctx.globalAlpha = p.alpha * (p.life / p.maxLife) * p.fadeIn;
      ctx.fillStyle = p.color;

      switch (p.shape) {
        case "circle":
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
          ctx.fill();
          break;
        case "square":
          ctx.fillRect(
            p.x - p.size,
            p.y - p.size,
            p.size * 2,
            p.size * 2
          );
          break;
        case "diamond":
          ctx.beginPath();
          ctx.moveTo(p.x, p.y - p.size);
          ctx.lineTo(p.x + p.size, p.y);
          ctx.lineTo(p.x, p.y + p.size);
          ctx.lineTo(p.x - p.size, p.y);
          ctx.closePath();
          ctx.fill();
          break;
      }

      ctx.restore();
    };

    let animId = 0;
    let isRunning = false;

    const animate = () => {
      isRunning = true;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.life--;

        if (p.fadeIn < 1) {
          p.fadeIn = Math.min(1, p.fadeIn + 1 / 30);
        }

        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

        if (p.life <= 0) {
          particles.splice(i, 1);
          createParticle();
          continue;
        }

        drawParticle(p);
      }

      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance < 150) {
            ctx.save();
            ctx.globalAlpha = (1 - distance / 150) * 0.1;
            ctx.strokeStyle = color;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
            ctx.restore();
          }
        }
      }

      animId = requestAnimationFrame(animate);
    };

    const start = () => {
      if (!isRunning) animate();
    };

    const stop = () => {
      if (animId) cancelAnimationFrame(animId);
      animId = 0;
      isRunning = false;
    };

    const handleVisibility = () => {
      if (document.visibilityState === "hidden") {
        stop();
      } else {
        start();
      }
    };

    document.addEventListener("visibilitychange", handleVisibility);
    start();

    return () => {
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", handleVisibility);
      stop();
    };
  }, [color, count, speed, size]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none"
      style={{ zIndex: 1 }}
    />
  );
}
