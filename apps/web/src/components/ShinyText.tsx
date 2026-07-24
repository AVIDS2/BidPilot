import { cn } from "@/lib/utils";

/** Static text shell: shiny gradient animation removed. */
export default function ShinyText({
  text,
  className,
  color,
  muted,
}: {
  text: string;
  disabled?: boolean;
  speed?: number;
  className?: string;
  color?: string;
  shineColor?: string;
  spread?: number;
  muted?: boolean;
}) {
  return (
    <span
      className={cn(muted ? "text-muted-foreground" : "text-foreground", className)}
      style={color ? { color } : undefined}
    >
      {text}
    </span>
  );
}
