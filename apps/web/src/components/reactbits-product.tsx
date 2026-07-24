import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Quiet product wrappers.
 *
 * Historical ReactBits electric/glare/spark motion was removed for Operate UI.
 * These helpers remain as stable import targets so marketing and product pages
 * keep compiling while rendering plain, accessible structure.
 */

export function ProductReveal({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  blur?: boolean;
}) {
  return <div className={className}>{children}</div>;
}

export function ProductGlareCard({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
  intense?: boolean;
}) {
  return <div className={cn("min-w-0", className)}>{children}</div>;
}

export function ProductElectricFrame({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
  active?: boolean;
  radius?: number;
}) {
  return <div className={className}>{children}</div>;
}

export function ProductShinyText({
  text,
  className,
  muted = false,
}: {
  text: string;
  className?: string;
  muted?: boolean;
}) {
  return (
    <span
      className={cn(
        muted ? "text-muted-foreground" : "text-foreground",
        className,
      )}
    >
      {text}
    </span>
  );
}
