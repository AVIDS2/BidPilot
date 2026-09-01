import { describe, expect, it } from 'vitest';
import { acceptRuntimeProjection, mergeAssistantMessages, type ChatMessage } from './agent-store';

const message = (overrides: Partial<ChatMessage>): ChatMessage => ({
  id: 'local',
  role: 'user',
  content: '你好',
  timestamp: 1,
  ...overrides
});

describe('mergeAssistantMessages', () => {
  it('does not duplicate an optimistic user message after durable history arrives', () => {
    const current = [message({ id: 'optimistic-user', durableId: 'user-1' })];
    const incoming = [message({ id: 'user-1', durableId: 'user-1', timestamp: 2 })];

    const merged = mergeAssistantMessages(current, incoming);

    expect(merged).toHaveLength(1);
    expect(merged[0].id).toBe('user-1');
  });

  it('does not duplicate an optimistic assistant message after runtime history arrives', () => {
    const current = [
      message({
        id: 'optimistic-assistant',
        role: 'assistant',
        content: '你好',
        runtimeRunId: 'run-1'
      })
    ];
    const incoming = [
      message({
        id: 'assistant-1',
        role: 'assistant',
        content: '你好！',
        runtimeRunId: 'run-1',
        timestamp: 2
      })
    ];

    const merged = mergeAssistantMessages(current, incoming);

    expect(merged).toHaveLength(1);
    expect(merged[0].id).toBe('assistant-1');
    expect(merged[0].content).toBe('你好！');
  });
});

describe('acceptRuntimeProjection', () => {
  it('keeps multiple projections from one durable event idempotent', () => {
    const cursors: Record<string, number> = {};
    const seen = new Set<string>();
    const base = {
      runtime_run_id: 'run-1',
      runtime_event_id: 'event-1',
      runtime_sequence: 2
    };

    expect(acceptRuntimeProjection(cursors, seen, 'assistant.workflow_started', base)).toBe(true);
    expect(acceptRuntimeProjection(cursors, seen, 'assistant.tool_succeeded', base)).toBe(true);
    expect(acceptRuntimeProjection(cursors, seen, 'assistant.workflow_started', base)).toBe(false);
    expect(cursors).toEqual({ 'run-1': 2 });
  });

  it('allows a missed lower-sequence frame during full replay', () => {
    const cursors: Record<string, number> = { 'run-1': 4 };
    const seen = new Set<string>();
    expect(
      acceptRuntimeProjection(cursors, seen, 'assistant.tool_succeeded', {
        runtime_run_id: 'run-1',
        runtime_event_id: 'event-3',
        runtime_sequence: 3
      })
    ).toBe(true);
  });

  it('collapses a live Pi tool frame into its durable replay frame', () => {
    const cursors: Record<string, number> = {};
    const seen = new Set<string>();
    expect(
      acceptRuntimeProjection(cursors, seen, 'assistant.tool_started', {
        runtime_run_id: 'run-1',
        tool_call_id: 'call-1'
      })
    ).toBe(true);
    expect(
      acceptRuntimeProjection(cursors, seen, 'assistant.tool_started', {
        runtime_run_id: 'run-1',
        runtime_event_id: 'event-1',
        runtime_sequence: 9,
        tool_call_id: 'call-1'
      })
    ).toBe(false);
    expect(cursors).toEqual({ 'run-1': 9 });
  });
});
