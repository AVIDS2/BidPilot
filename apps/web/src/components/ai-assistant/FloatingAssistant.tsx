import { useState, useRef, useCallback, useEffect } from "react";
import {
  MessageCircleIcon,
  CommandIcon,
  PanelRightOpenIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { isAssistantBusy, useAIAssistant } from "@/lib/ai-assistant-store";
import { cn } from "@/lib/utils";
import { AgentMark } from "@/components/brand";

/**
 * Floating assistant ball.
 * - Click: toggles side panel
 * - Right-click / long-press: shows quick-access radial menu
 * - Shows status ring: idle = subtle pulse, processing = spinning gradient
 */
export function FloatingAssistant() {
  const { state, toggle } = useAIAssistant();
  const { t } = useTranslation("ai-assistant");
  const [showMenu, setShowMenu] = useState(false);
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  /* close menu on outside click */
  useEffect(() => {
    if (!showMenu) return;
    function handle(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [showMenu]);

  const handlePointerDown = useCallback(() => {
    longPressTimer.current = setTimeout(() => {
      setShowMenu(true);
    }, 500);
  }, []);

  const handlePointerUp = useCallback(() => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  }, []);

  const handleClick = useCallback(() => {
    if (showMenu) return;
    toggle("panel");
  }, [showMenu, toggle]);

  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setShowMenu((v) => !v);
    },
    [],
  );

  /* hide when panel is open */
  if (state.isOpen && state.mode === "panel") return null;

  const isProcessing = isAssistantBusy(state.status);

  return (
    <div className="fixed bottom-[max(1rem,env(safe-area-inset-bottom))] right-4 z-50 sm:bottom-6 sm:right-6" ref={menuRef}>
      {/* ─── Radial quick menu ─── */}
      {showMenu && (
        <div
          className="absolute bottom-14 right-0 flex max-w-[calc(100vw-2rem)] flex-col items-end gap-2 animate-scale-in sm:bottom-16"
          style={{ transformOrigin: "bottom right" }}
        >
          <MenuAction
            icon={<PanelRightOpenIcon className="w-4 h-4" />}
            label={t("floating.openPanel")}
            onClick={() => {
              setShowMenu(false);
              toggle("panel");
            }}
          />
          <MenuAction
            icon={<CommandIcon className="w-4 h-4" />}
            label={t("floating.commandPalette")}
            onClick={() => {
              setShowMenu(false);
              toggle("command");
            }}
          />
          <MenuAction
            icon={<MessageCircleIcon className="w-4 h-4" />}
            label={t("floating.aiChat")}
            onClick={() => {
              setShowMenu(false);
              toggle("panel");
            }}
          />
        </div>
      )}

      {/* ─── Floating button ─── */}
      <button
        onClick={handleClick}
        onContextMenu={handleContextMenu}
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
        aria-label={t("floating.ariaLabel")}
        className={cn(
          "relative flex size-11 items-center justify-center rounded-[1.25rem] p-0 sm:size-12",
          "transition-all duration-300",
          "hover:scale-110 active:scale-95",
          "shadow-lg hover:shadow-xl",
          "outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        )}
      >
        {/* Spinning ring when processing */}
        {isProcessing && (
          <span
            className="absolute -inset-1 rounded-[1.45rem] animate-spin"
            style={{
              background:
                "conic-gradient(from 0deg, transparent 0%, var(--primary) 30%, transparent 60%)",
              mask: "radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 2px))",
              WebkitMask: "radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 2px))",
            }}
          />
        )}
        <AgentMark decorative className="relative z-10 size-full" />
      </button>
    </div>
  );
}

/* ─── Radial menu action item ─── */

function MenuAction({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex max-w-[calc(100vw-2rem)] items-center gap-2 rounded-xl px-3 py-2 text-sm whitespace-nowrap transition-all duration-200 hover:scale-105"
      style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        color: "var(--foreground)",
        boxShadow: "var(--shadow-lg)",
      }}
    >
      {icon}
      {label}
    </button>
  );
}
