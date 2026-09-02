import { describe, expect, it } from 'vitest';
import { getAssistantActivityLabel, getAssistantToolLabel } from './assistant-tool-metadata';
import type { AssistantExecutionItem } from '@/features/agent/state/agent-store';

const EN_TOOL_LABELS: Record<string, string> = {
  'activity.tool.list_claim_review_queue': 'Check claims awaiting review',
  'activity.tool.search_bid_wiki': 'Search Bid Wiki',
  'activity.tool.list_knowledge_portfolio': 'View knowledge portfolio',
  'activity.tool.propose_memory': 'Save personal preference',
  'activity.tool.forget_memory': 'Forget memory'
};

function translate(key: string, options?: Record<string, unknown>) {
  return EN_TOOL_LABELS[key] ?? String(options?.defaultValue ?? key);
}

describe('assistant tool metadata', () => {
  it('renders current knowledge and memory capabilities with user-facing labels', () => {
    for (const [toolName, expectedLabel] of Object.entries({
      list_claim_review_queue: 'Check claims awaiting review',
      search_bid_wiki: 'Search Bid Wiki',
      list_knowledge_portfolio: 'View knowledge portfolio',
      propose_memory: 'Save personal preference',
      forget_memory: 'Forget memory'
    })) {
      expect(getAssistantToolLabel(toolName, translate)).toBe(expectedLabel);
    }
  });

  it('uses structured Skill and MCP metadata for live activity labels', () => {
    const base: AssistantExecutionItem = {
      id: 'activity-1',
      kind: 'tool',
      toolName: 'read_skill',
      title: '载入流程技能',
      status: 'running',
      timestamp: 1
    };
    expect(
      getAssistantActivityLabel(
        { ...base, resourceKind: 'skill', resourceName: 'opportunity-deep-research' },
        translate
      )
    ).toBe('准备工作步骤');
    expect(
      getAssistantActivityLabel(
        { ...base, resourceKind: 'mcp', provider: 'mcp:tavily', toolName: 'mcp_tavily_search' },
        translate
      )
    ).toBe('查询外部资料');
  });
});
