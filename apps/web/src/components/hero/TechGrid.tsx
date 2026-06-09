import { useEffect, useRef } from "react";

interface TechGridProps {
  color?: string;
  opacity?: number;
  cellSize?: number;
  animated?: boolean;
}

export function TechGrid({
  color = "#84cc16",
  opacity = 0.1,
  cellSize = 50,
  animated = true,
}: TechGridProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const drawGrid = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const cx = canvas.width / 2;
      const cy = canvas.height / 2;
      const maxDist = Math.sqrt(cx * cx + cy * cy);

      const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, maxDist);
      gradient.addColorStop(0, "rgba(255, 255, 255, 1)");
      gradient.addColorStop(0.4, "rgba(255, 255, 255, 0.6)");
      gradient.addColorStop(1, "rgba(255, 255, 255, 0)");

      ctx.save();
      ctx.strokeStyle = color;
      ctx.globalAlpha = opacity;
      ctx.lineWidth = 0.5;

      for (let x = 0; x <= canvas.width; x += cellSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }

      for (let y = 0; y <= canvas.height; y += cellSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }

      ctx.globalAlpha = opacity * 2;
      for (let x = 0; x <= canvas.width; x += cellSize) {
        for (let y = 0; y <= canvas.height; y += cellSize) {
          ctx.beginPath();
          ctx.arc(x, y, 2, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
        }
      }
      ctx.restore();

      ctx.save();
      ctx.globalCompositeOperation = "destination-in";
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.restore();
    };

    if (animated) {
      let offset = 0;
      let animId: number;
      const animate = () => {
        ctx.save();
        ctx.translate(0, offset);
        drawGrid();
        ctx.restore();
        offset = (offset + 0.5) % cellSize;
        animId = requestAnimationFrame(animate);
      };
      animate();
      return () => {
        window.removeEventListener("resize", resize);
        cancelAnimationFrame(animId);
      };
    } else {
      drawGrid();
      return () => window.removeEventListener("resize", resize);
    }
  }, [color, opacity, cellSize, animated]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none"
      style={{ zIndex: 0 }}
    />
  );
}
