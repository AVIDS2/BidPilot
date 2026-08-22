import { useEffect } from "react";
import { useAIAssistant } from "@/features/agent/state/agent-store";

/**
 * Global hotkeys for the AI assistant platform.
 *
 *   Cmd/Ctrl + K          -> command palette
 *   Cmd/Ctrl + Shift + A  -> toggle side panel
 *   Escape                -> close whatever is open
 */
export function useAIAssistantHotkeys() {
  const { state, toggle, close } = useAIAssistant();

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const mod = e.metaKey || e.ctrlKey;

      // Cmd/Ctrl + K -> command palette
      if (mod && e.key === "k") {
        e.preventDefault();
        toggle("command");
        return;
      }

      // Cmd/Ctrl + Shift + A -> side panel
      if (mod && e.shiftKey && e.key.toLowerCase() === "a") {
        e.preventDefault();
        toggle("panel");
        return;
      }

      // Escape -> close
      if (e.key === "Escape" && state.isOpen) {
        e.preventDefault();
        close();
        return;
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [state.isOpen, toggle, close]);
}
