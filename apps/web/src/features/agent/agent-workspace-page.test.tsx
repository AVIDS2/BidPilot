import { render, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const dispatch = vi.fn();

vi.mock('@/features/agent/state/agent-store', () => ({
  isAssistantBusy: () => false,
  useAIAssistant: () => ({
    dispatch,
    loadConversation: vi.fn().mockResolvedValue(undefined),
    sendMessage: vi.fn().mockResolvedValue(undefined),
    state: {
      currentConversationId: null,
      messages: [],
      status: 'idle'
    }
  })
}));

vi.mock('./linear-agent-workspace', () => ({
  LinearAgentWorkspace: () => <div data-testid='agent-workspace' />
}));

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams('project_id=project-123')
}));

import { AgentWorkspacePage } from './agent-workspace-page';

describe('AgentWorkspacePage', () => {
  it('keeps the source project context when opened from a project workspace', async () => {
    dispatch.mockClear();
    render(<AgentWorkspacePage />);

    await waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith({
        type: 'SET_CONTEXT',
        context: { page: 'agent', projectId: 'project-123' }
      });
    });
  });
});
