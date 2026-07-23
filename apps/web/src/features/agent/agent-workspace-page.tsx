import { AIAssistantPanel } from "@/components/ai-assistant/AIAssistantPanel";

/**
 * The full-page operator reuses the same conversation and Runtime event state
 * as the contextual side panel. It is a workspace surface, not a second chat.
 */
export function AgentWorkspacePage() {
  return (
    <section
      className="flex min-h-0 w-full min-w-0 flex-1 flex-col"
      aria-label="BidPilot Agent workspace"
    >
      <h2 className="sr-only">BidPilot AI</h2>
      <div className="mx-auto flex min-h-0 w-full min-w-0 max-w-[1120px] flex-1 flex-col">
        <AIAssistantPanel variant="workspace" />
      </div>
    </section>
  );
}
