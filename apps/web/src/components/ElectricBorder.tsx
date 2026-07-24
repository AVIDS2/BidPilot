import type { ReactNode, HTMLAttributes, CSSProperties } from "react";
import { cn } from "@/lib/utils";

/** No-op shell: animated blue/violet lightning border removed. */
export type ElectricBorderProps = {
  children?: ReactNode;
  color?: string;
  speed?: number;
  chaos?: number;
  thickness?: number;
  className?: string;
  style?: CSSProperties;
  borderRadius?: number;
} & HTMLAttributes<HTMLDivElement>;

export default function ElectricBorder({
  children,
  className,
  style,
  ...props
}: ElectricBorderProps) {
  return (
    <div className={cn(className)} style={style} {...props}>
      {children}
    </div>
  );
}
