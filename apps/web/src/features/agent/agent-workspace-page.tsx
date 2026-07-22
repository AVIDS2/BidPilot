import { AIAssistantPanel } from "@/components/ai-assistant/AIAssistantPanel";

/**
 * The full-page operator reuses the same conversation and Runtime event state
 * as the contextual side panel. It is a workspace surface, not a second chat.
 */
export function AgentWorkspacePage() {
  return (
    <section className="mx-auto w-full max-w-[1120px]" aria-label="BidPilot Agent workspace">
      <h2 className="sr-only">BidPilot AI</h2>
      <AIAssistantPanel variant="workspace" />
    </section>
  );
}
