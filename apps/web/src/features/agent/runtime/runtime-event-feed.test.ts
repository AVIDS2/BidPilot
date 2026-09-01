import { describe, expect, it } from 'vitest';
import {
  advanceRuntimeEventCursor,
  advanceRuntimeSequenceCursor,
  isRuntimeEventNewer,
  isRuntimeSequenceNewer,
  isTerminalRuntimeEvent,
  recoverRuntimeMessageFromEvents,
  runtimeEventToAssistantEvents,
  type RuntimeEventRead
} from './runtime-event-feed';

function runtimeEvent(overrides: Partial<RuntimeEventRead> = {}): RuntimeEventRead {
  return {
    run_id: 'runtime-1',
    sequence: 2,
    type: 'capability.succeeded',
    public_summary: '找到 2 个项目。',
    payload: { capability: 'search_projects', count: 2 },
    schema_version: '1.0',
    ...overrides
  };
}

describe('runtime event feed', () => {
  it('advances a cursor only for a newer event in the same run', () => {
    const first = runtimeEvent({ sequence: 2 });
    const cursor = advanceRuntimeEventCursor({}, first);

    expect(cursor).toEqual({ 'runtime-1': 2 });
    expect(isRuntimeEventNewer(cursor, runtimeEvent({ sequence: 2 }))).toBe(false);
    expect(advanceRuntimeEventCursor(cursor, runtimeEvent({ sequence: 1 }))).toBe(cursor);
    expect(advanceRuntimeEventCursor(cursor, runtimeEvent({ sequence: 3 }))).toEqual({
      'runtime-1': 3
    });
    expect(isRuntimeSequenceNewer(cursor, 'runtime-1', 2)).toBe(false);
    expect(advanceRuntimeSequenceCursor(cursor, 'runtime-1', 4)).toEqual({ 'runtime-1': 4 });
  });

  it('translates a public capability result without leaking a raw tool dump', () => {
    const events = runtimeEventToAssistantEvents(runtimeEvent(), 'conversation-1');

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      eventType: 'assistant.tool_succeeded',
      data: {
        runtime_run_id: 'runtime-1',
        runtime_sequence: 2,
        tool_name: 'search_projects',
        result: { count: 2 },
        summary: '找到 2 个项目。',
        state: 'completed'
      }
    });
  });

  it('marks only terminal lifecycle events as terminal', () => {
    expect(isTerminalRuntimeEvent(runtimeEvent({ type: 'run.completed' }))).toBe(true);
    expect(isTerminalRuntimeEvent(runtimeEvent({ type: 'run.failed' }))).toBe(true);
    expect(isTerminalRuntimeEvent(runtimeEvent({ type: 'capability.started' }))).toBe(false);
  });

  it('replays a durable harness execution plan before the capability starts', () => {
    const events = runtimeEventToAssistantEvents(
      runtimeEvent({
        event_id: 'event-plan-1',
        parent_event_id: 'event-turn-1',
        type: 'plan.proposed',
        public_summary: '执行计划：入库远程资料。',
        payload: {
          stage: 'tool_plan',
          turn_id: 'turn-1',
          items: [
            {
              id: 'call-1',
              capability: 'fetch_url_to_project',
              title: '入库远程资料',
              status: 'planned'
            }
          ]
        }
      }),
      'conversation-1'
    );

    expect(events).toEqual([
      {
        eventType: 'assistant.plan_updated',
        data: {
          runtime_run_id: 'runtime-1',
          runtime_event_id: 'event-plan-1',
          runtime_parent_event_id: 'event-turn-1',
          runtime_sequence: 2,
          turn_id: 'turn-1',
          summary: '执行计划：入库远程资料。',
          items: [
            {
              id: 'call-1',
              capability: 'fetch_url_to_project',
              title: '入库远程资料',
              status: 'planned'
            }
          ],
          state: 'thinking'
        }
      }
    ]);
  });

  it('projects a durable approval boundary into one confirmation and one pause', () => {
    const events = runtimeEventToAssistantEvents(
      runtimeEvent({
        event_id: 'event-approval-1',
        parent_event_id: 'event-turn-1',
        type: 'approval.requested',
        public_summary: '创建项目需要你的确认。',
        payload: {
          action_id: 'action-1',
          approval_id: 'approval-1',
          capability: 'create_project',
          turn_id: 'turn-1',
          title: '创建项目',
          arguments: { name: '投标项目' },
          message: '确认创建项目「投标项目」吗？'
        }
      }),
      'conversation-1'
    );

    expect(events).toEqual([
      {
        eventType: 'assistant.confirmation_requested',
        data: {
          runtime_run_id: 'runtime-1',
          runtime_event_id: 'event-approval-1',
          runtime_parent_event_id: 'event-turn-1',
          runtime_sequence: 2,
          conversation_id: 'conversation-1',
          approval_id: 'approval-1',
          tool_name: 'create_project',
          tool_call_id: 'action-1',
          turn_id: 'turn-1',
          title: '创建项目',
          arguments: { name: '投标项目' },
          message: '确认创建项目「投标项目」吗？',
          requires_typed_confirmation: false,
          state: 'needs_confirmation'
        }
      },
      {
        eventType: 'assistant.end',
        data: {
          runtime_run_id: 'runtime-1',
          runtime_event_id: 'event-approval-1',
          runtime_parent_event_id: 'event-turn-1',
          runtime_sequence: 2,
          conversation_id: 'conversation-1',
          state: 'needs_confirmation'
        }
      }
    ]);
  });

  it('does not duplicate a final message after durable deltas were rendered', () => {
    const delta = runtimeEventToAssistantEvents(
      runtimeEvent({
        event_id: 'event-message-1',
        type: 'message.delta',
        public_summary: '项目已创建。',
        payload: { turn_id: 'turn-1' }
      }),
      'conversation-1'
    );
    const completed = runtimeEventToAssistantEvents(
      runtimeEvent({
        event_id: 'event-message-2',
        parent_event_id: 'event-turn-1',
        sequence: 3,
        type: 'message.completed',
        public_summary: '项目已创建。',
        payload: { turn_id: 'turn-1', delta_emitted: true }
      }),
      'conversation-1'
    );

    expect(delta).toHaveLength(1);
    expect(delta[0].data.content).toBe('项目已创建。');
    expect(completed).toEqual([]);
  });

  it('recovers a completed message even when delta replay was intentionally suppressed', () => {
    const recovered = recoverRuntimeMessageFromEvents('runtime-1', [
      runtimeEvent({
        sequence: 4,
        type: 'message.delta',
        public_summary: '当前有 ',
        timestamp: '2026-08-06T01:00:00.000Z'
      }),
      runtimeEvent({
        sequence: 5,
        type: 'message.delta',
        public_summary: '3 个项目。',
        timestamp: '2026-08-06T01:00:00.100Z'
      }),
      runtimeEvent({
        sequence: 6,
        type: 'message.completed',
        public_summary: '当前有 3 个项目。',
        payload: { delta_emitted: true },
        timestamp: '2026-08-06T01:00:00.200Z'
      })
    ]);

    expect(recovered).toEqual({
      runId: 'runtime-1',
      content: '当前有 3 个项目。',
      timestamp: Date.parse('2026-08-06T01:00:00.200Z')
    });
  });

  it('falls back to concatenated message deltas for an interrupted terminal event', () => {
    expect(
      recoverRuntimeMessageFromEvents('runtime-1', [
        runtimeEvent({ type: 'message.delta', public_summary: '回复的' }),
        runtimeEvent({ type: 'message.delta', public_summary: '一部分' })
      ])
    ).toMatchObject({ runId: 'runtime-1', content: '回复的一部分' });
  });

  it('preserves provider whitespace kept in the durable delta payload', () => {
    const recovered = recoverRuntimeMessageFromEvents('runtime-1', [
      runtimeEvent({
        type: 'message.delta',
        public_summary: '你好',
        payload: { delta: '你好' }
      }),
      runtimeEvent({
        type: 'message.delta',
        public_summary: '世界',
        payload: { delta: ' 世界' }
      })
    ]);

    expect(recovered).toMatchObject({ runId: 'runtime-1', content: '你好 世界' });
  });

  it('maps Harness-authored reasoning into chronological assistant events', () => {
    const delta = runtimeEventToAssistantEvents(
      runtimeEvent({
        event_id: 'event-reasoning-1',
        type: 'reasoning.delta',
        public_summary: '先核对项目资料与已上传文件。',
        payload: { turn_id: 'turn-1', source: 'harness' }
      }),
      'conversation-1'
    );
    const completed = runtimeEventToAssistantEvents(
      runtimeEvent({
        event_id: 'event-reasoning-2',
        parent_event_id: 'event-reasoning-1',
        sequence: 3,
        type: 'reasoning.completed',
        public_summary: '',
        payload: { turn_id: 'turn-1', source: 'harness' }
      }),
      'conversation-1'
    );

    expect(delta).toEqual([
      {
        eventType: 'assistant.reasoning',
        data: {
          runtime_run_id: 'runtime-1',
          runtime_event_id: 'event-reasoning-1',
          runtime_sequence: 2,
          turn_id: 'turn-1',
          content: '先核对项目资料与已上传文件。',
          title: '先核对项目资料与已上传文件。',
          source: 'harness',
          state: 'thinking'
        }
      }
    ]);
    expect(completed).toEqual([
      {
        eventType: 'assistant.reasoning_completed',
        data: {
          runtime_run_id: 'runtime-1',
          runtime_event_id: 'event-reasoning-2',
          runtime_parent_event_id: 'event-reasoning-1',
          runtime_sequence: 3,
          turn_id: 'turn-1',
          source: 'harness',
          state: 'thinking'
        }
      }
    ]);
  });

  it('does not replay raw provider thought into the conversation', () => {
    const events = runtimeEventToAssistantEvents(
      runtimeEvent({
        type: 'reasoning.delta',
        public_summary: 'The system prompt says to call a tool.',
        payload: { turn_id: 'turn-1', source: 'provider' }
      }),
      'conversation-1'
    );

    expect(events).toEqual([]);
  });

  it('preserves Harness-authored narration without matching its text', () => {
    const events = runtimeEventToAssistantEvents(
      runtimeEvent({
        type: 'reasoning.delta',
        public_summary: '为推进当前任务，我先导出交付物，再根据真实结果决定下一步。',
        payload: { turn_id: 'turn-1', source: 'harness' }
      }),
      'conversation-1'
    );

    expect(events).toEqual([
      {
        eventType: 'assistant.reasoning',
        data: expect.objectContaining({
          content: '为推进当前任务，我先导出交付物，再根据真实结果决定下一步。',
          runtime_run_id: 'runtime-1',
          runtime_sequence: 2,
          turn_id: 'turn-1'
        })
      }
    ]);
  });

  it('treats an entity-relation proposal as a workflow without exposing source details', () => {
    const events = runtimeEventToAssistantEvents(
      runtimeEvent({
        payload: {
          capability: 'propose_memory_graph',
          run_id: 'execution-run-1',
          runtime_run_id: 'workflow-run-1',
          reused: false
        },
        public_summary: '实体关系提案已启动。'
      }),
      'conversation-1'
    );

    expect(events).toEqual([
      {
        eventType: 'assistant.workflow_started',
        data: {
          runtime_run_id: 'runtime-1',
          runtime_sequence: 2,
          tool_name: 'propose_memory_graph',
          result: {
            run_id: 'execution-run-1',
            runtime_run_id: 'workflow-run-1',
            reused: false
          },
          state: 'running_workflow'
        }
      },
      {
        eventType: 'assistant.tool_succeeded',
        data: {
          runtime_run_id: 'runtime-1',
          runtime_sequence: 2,
          tool_name: 'propose_memory_graph',
          result: {
            run_id: 'execution-run-1',
            runtime_run_id: 'workflow-run-1',
            reused: false
          },
          summary: '实体关系提案已启动。',
          state: 'completed'
        }
      }
    ]);
  });

  it('translates provider retry and terminal failure with stable recovery codes', () => {
    const retryEvents = runtimeEventToAssistantEvents(
      runtimeEvent({
        type: 'capability.progressed',
        public_summary: '模型服务暂时不可用，正在重试。',
        payload: {
          capability: 'section_drafter',
          node: 'section_drafter',
          phase: 'provider_retry',
          error_code: 'provider_rate_limited',
          next_attempt: 2,
          max_attempts: 3
        }
      }),
      'conversation-1'
    );
    expect(retryEvents).toEqual([
      {
        eventType: 'assistant.workflow_provider_retry',
        data: {
          runtime_run_id: 'runtime-1',
          runtime_sequence: 2,
          tool_name: 'section_drafter',
          node_name: 'section_drafter',
          error_code: 'provider_rate_limited',
          retry_attempt: 2,
          retry_max_attempts: 3,
          state: 'running_workflow'
        }
      }
    ]);

    const failureEvents = runtimeEventToAssistantEvents(
      runtimeEvent({
        type: 'run.failed',
        public_summary: '工作流未能完成。',
        payload: { error_code: 'provider_auth_failed' }
      }),
      'conversation-1'
    );
    expect(failureEvents).toEqual([
      {
        eventType: 'assistant.workflow_failed',
        data: {
          runtime_run_id: 'runtime-1',
          runtime_sequence: 2,
          tool_name: 'workflow',
          error_message: '工作流未能完成。',
          error_code: 'provider_auth_failed',
          state: 'failed'
        }
      },
      {
        eventType: 'assistant.end',
        data: {
          runtime_run_id: 'runtime-1',
          runtime_sequence: 2,
          conversation_id: 'conversation-1',
          state: 'failed'
        }
      }
    ]);
  });

  it('does not recover a terminal failure as a normal assistant message', () => {
    expect(
      recoverRuntimeMessageFromEvents('runtime-1', [
        runtimeEvent({
          type: 'message.completed',
          public_summary: '模型运行未能完成。',
          payload: { terminal_failure: true }
        })
      ])
    ).toBeNull();
  });

  it("keeps a failed assistant turn's partial answer separate from its terminal error", () => {
    const events = runtimeEventToAssistantEvents(
      runtimeEvent({
        type: 'run.failed',
        public_summary: '任务未能完成。',
        payload: {
          kind: 'assistant_turn',
          message: '助手运行未完成，已安全停止。',
          message_delta_emitted: true,
          error_code: 'assistant_stream_incomplete'
        }
      }),
      'conversation-1'
    );

    expect(events).toEqual([
      {
        eventType: 'assistant.session_error',
        data: expect.objectContaining({
          message: '助手运行未完成，已安全停止。',
          error_code: 'assistant_stream_incomplete',
          state: 'failed'
        })
      },
      {
        eventType: 'assistant.end',
        data: expect.objectContaining({
          conversation_id: 'conversation-1',
          state: 'failed'
        })
      }
    ]);
  });

  it('carries a durable tool call id into both capability lifecycle events', () => {
    const events = runtimeEventToAssistantEvents(
      runtimeEvent({
        type: 'capability.started',
        payload: {
          capability: 'search_projects',
          action_id: 'action-1',
          tool_call_id: 'pi-call-1',
          turn_id: 'turn-1'
        }
      })
    );

    expect(events[0]?.data).toEqual(
      expect.objectContaining({
        tool_call_id: 'pi-call-1',
        turn_id: 'turn-1'
      })
    );
  });

  it('maps Pi subagent tool lifecycle without exposing arguments or raw results', () => {
    const started = runtimeEventToAssistantEvents(
      runtimeEvent({
        type: 'capability.progressed',
        public_summary: '子 Agent 正在调用 web_search。',
        payload: {
          capability: 'subagent',
          phase: 'tool_started',
          tool: 'web_search',
          tool_call_id: 'child-call-1',
          arguments: { query: '不得进入 UI' }
        }
      })
    );
    const completed = runtimeEventToAssistantEvents(
      runtimeEvent({
        sequence: 3,
        type: 'capability.progressed',
        public_summary: '子 Agent 已完成 web_search。',
        payload: {
          capability: 'subagent',
          phase: 'tool_completed',
          tool: 'web_search',
          tool_call_id: 'child-call-1',
          result: { items: ['不得进入 UI'] }
        }
      })
    );

    expect(started).toEqual([
      {
        eventType: 'assistant.tool_started',
        data: {
          runtime_run_id: 'runtime-1',
          runtime_sequence: 2,
          tool_name: 'web_search',
          tool_call_id: 'child-call-1',
          title: '子 Agent 正在调用 web_search。',
          state: 'executing_tool'
        }
      }
    ]);
    expect(completed).toEqual([
      {
        eventType: 'assistant.tool_succeeded',
        data: {
          runtime_run_id: 'runtime-1',
          runtime_sequence: 3,
          tool_name: 'web_search',
          tool_call_id: 'child-call-1',
          summary: '子 Agent 已完成 web_search。',
          state: 'completed'
        }
      }
    ]);
  });

  it('maps a structured deep-research session without inspecting narration', () => {
    const [started] = runtimeEventToAssistantEvents(
      runtimeEvent({
        type: 'plan.updated',
        public_summary: '已加载调研方法。',
        payload: {
          stage: 'task_started',
          task_title: '招标机会深度调研',
          presentation_kind: 'deep_research',
          presentation_session_id: 'research-session-1',
          presentation_title: '招标机会深度调研'
        }
      })
    );

    expect(started).toEqual({
      eventType: 'assistant.task_started',
      data: expect.objectContaining({
        presentation_kind: 'deep_research',
        presentation_session_id: 'research-session-1',
        presentation_title: '招标机会深度调研'
      })
    });
  });

  it('maps child identities as soon as durable subagents are created', () => {
    const events = runtimeEventToAssistantEvents(
      runtimeEvent({
        type: 'capability.progressed',
        public_summary: '已派生 2 个子 Agent。',
        payload: {
          capability: 'subagent',
          phase: 'children_spawned',
          children: [
            { run_id: 'child-1', profile: 'researcher', status: 'queued' },
            { run_id: 'child-2', profile: 'reviewer', status: 'queued' }
          ]
        }
      })
    );

    expect(events).toEqual([
      {
        eventType: 'assistant.subagents_spawned',
        data: expect.objectContaining({
          runtime_run_id: 'runtime-1',
          children: expect.arrayContaining([
            expect.objectContaining({ run_id: 'child-1' }),
            expect.objectContaining({ run_id: 'child-2' })
          ])
        })
      }
    ]);
  });

  it('projects deep-research phases as one live runtime instead of search rows', () => {
    const [progress] = runtimeEventToAssistantEvents(
      runtimeEvent({
        type: 'capability.progressed',
        public_summary: '已收集来源，开始读取正文。',
        payload: {
          capability: 'deep_research',
          phase: 'retrieve',
          presentation_kind: 'deep_research',
          presentation_session_id: 'research-1',
          presentation_title: '深度调研',
          source_count: 4
        }
      })
    );

    expect(progress).toEqual({
      eventType: 'assistant.deep_research_progress',
      data: expect.objectContaining({
        tool_name: 'start_deep_research',
        phase: 'retrieve',
        result: expect.objectContaining({ source_count: 4 }),
        presentation_kind: 'deep_research'
      })
    });

    const terminal = runtimeEventToAssistantEvents(
      runtimeEvent({
        type: 'run.completed',
        public_summary: '研究报告已生成。',
        payload: {
          capability: 'deep_research',
          presentation_kind: 'deep_research',
          result: {
            report: '# 研究报告',
            source_count: 4,
            claim_count: 2
          }
        }
      })
    );
    expect(terminal[0]).toEqual({
      eventType: 'assistant.deep_research_completed',
      data: expect.objectContaining({
        result: { report: '# 研究报告', source_count: 4, claim_count: 2 },
        state: 'completed'
      })
    });
  });
});
