'use client';

import { AIAssistantProvider } from '@/features/agent/state/agent-store';
import { AgentWorkspacePage } from '@/features/agent/agent-workspace-page';

export default function AgentPage() {
  return (
    <AIAssistantProvider>
      <AgentWorkspacePage />
    </AIAssistantProvider>
  );
}
