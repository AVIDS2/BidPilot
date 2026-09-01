import type { ReactNode, HTMLAttributes, CSSProperties } from 'react';
import { cn } from '@/lib/utils';

/** Static shell: blur/fade intersection choreography removed. */
export type FadeContentProps = {
  children?: ReactNode;
  blur?: boolean;
  duration?: number;
  easing?: string;
  delay?: number;
  threshold?: number;
  initialOpacity?: number;
  className?: string;
  style?: CSSProperties;
} & HTMLAttributes<HTMLDivElement>;

export default function FadeContent({ children, className, style, ...props }: FadeContentProps) {
  return (
    <div className={cn(className)} style={style} {...props}>
      {children}
    </div>
  );
}
