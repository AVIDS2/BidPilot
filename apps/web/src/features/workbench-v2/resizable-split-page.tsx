import {
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";

import { cn } from "@/lib/utils";

type ResizableSplitPageProps = {
  children: ReactNode;
  className: string;
  labelledBy: string;
  storageKey: string;
  minWidth?: number;
  maxWidth?: number;
  defaultWidth?: number;
};

const RESIZE_LAYOUT_VERSION = "v2";

function clampWidth(value: number, minWidth: number, maxWidth: number) {
  return Math.min(maxWidth, Math.max(minWidth, value));
}

function savedWidth(storageKey: string, minWidth: number, maxWidth: number) {
  const stored = Number(window.localStorage.getItem(storageKey));
  return Number.isFinite(stored) && stored > 0
    ? clampWidth(stored, minWidth, maxWidth)
    : null;
}

// Keep the source layout proportional until a person deliberately resizes it.
// A saved pixel width is only an interaction preference, never the initial layout.
export function ResizableSplitPage({
  children,
  className,
  labelledBy,
  storageKey,
  minWidth = 252,
  maxWidth = 520,
  defaultWidth = 330,
}: ResizableSplitPageProps) {
  // Layout defaults stay proportional to the source reference.  A saved width is
  // only applied after a person has deliberately dragged this version of the split.
  const preferenceKey = `${storageKey}.${RESIZE_LAYOUT_VERSION}`;
  const [listWidth, setListWidth] = useState<number | null>(() => savedWidth(preferenceKey, minWidth, maxWidth));
  const [isResizing, setIsResizing] = useState(false);
  const isDraggingRef = useRef(false);

  useEffect(() => {
    if (listWidth !== null) {
      window.localStorage.setItem(preferenceKey, String(listWidth));
    }
  }, [listWidth, preferenceKey]);

  const finishResize = () => {
    isDraggingRef.current = false;
    setIsResizing(false);
  };

  const handleResizeStart = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    isDraggingRef.current = true;
    setIsResizing(true);
  };

  const handleResizeMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!isDraggingRef.current) return;
    const page = event.currentTarget.parentElement;
    if (!page) return;
    setListWidth(clampWidth(event.clientX - page.getBoundingClientRect().left, minWidth, maxWidth));
  };

  return (
    <section
      aria-labelledby={labelledBy}
      className={cn("wb-page", "wb-split-page", className, isResizing && "is-resizing")}
      style={listWidth === null ? undefined : { "--wb-split-list-width": `${listWidth}px` } as CSSProperties}
    >
      {children}
      <div
        aria-label="调整列表宽度"
        aria-orientation="vertical"
        aria-valuemax={maxWidth}
        aria-valuemin={minWidth}
        aria-valuenow={listWidth ?? defaultWidth}
        className="wb-split-resize-handle"
        onDoubleClick={() => setListWidth(null)}
        onKeyDown={(event) => {
          if (event.key === "ArrowLeft") {
            event.preventDefault();
            setListWidth((width) => clampWidth((width ?? defaultWidth) - 16, minWidth, maxWidth));
          }
          if (event.key === "ArrowRight") {
            event.preventDefault();
            setListWidth((width) => clampWidth((width ?? defaultWidth) + 16, minWidth, maxWidth));
          }
        }}
        onPointerCancel={finishResize}
        onPointerDown={handleResizeStart}
        onLostPointerCapture={finishResize}
        onPointerMove={handleResizeMove}
        onPointerUp={finishResize}
        role="separator"
        tabIndex={0}
        title="拖动调整列表宽度；双击恢复默认布局"
      />
    </section>
  );
}
