import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { AIAssistantProvider, useAIAssistant } from '@/features/agent/state/agent-store';
import { AIAssistantPanel } from './AIAssistantPanel';

vi.mock('@/lib/api', () => ({
  listChatConversations: vi.fn().mockResolvedValue([]),
  listProviderConfigs: vi.fn().mockResolvedValue({ data: [] }),
  getChatConversationMessages: vi.fn(),
  renameChatConversation: vi.fn(),
  deleteChatConversation: vi.fn(),
  listBundles: vi.fn().mockResolvedValue([]),
  createBundle: vi.fn(),
  uploadDocument: vi.fn(),
  uploadAssistantAttachment: vi.fn(),
  downloadAssistantArtifact: vi.fn(),
  listRuntimeRuns: vi.fn().mockResolvedValue({ items: [], next_cursor: null }),
  listRuntimeChildRuns: vi.fn().mockResolvedValue([]),
  listRuntimeEvents: vi.fn().mockResolvedValue({ items: [] }),
  cancelRuntimeWorkflow: vi.fn()
}));

function streamFrom(text: string) {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    }
  });
}

function OpenPanelButton() {
  const { open } = useAIAssistant();
  return <button onClick={() => open('panel')}>Open assistant</button>;
}

function renderPanel() {
  return render(
    <AIAssistantProvider>
      <OpenPanelButton />
      <AIAssistantPanel />
    </AIAssistantProvider>
  );
}

async function expandActivityDetails() {
  // Completed task turns stay collapsed until the reader asks for them.
  await waitFor(() => {
    expect(document.querySelector('.cr-task-turn-summary')).toBeTruthy();
  });
  const summary = document.querySelector<HTMLButtonElement>('.cr-task-turn-summary');
  if (!summary) throw new Error('Task turn summary was not rendered');
  if (summary.getAttribute('aria-expanded') === 'true') {
    return;
  }
  fireEvent.click(summary);
  await waitFor(() => {
    expect(summary).toHaveAttribute('aria-expanded', 'true');
  });
}

async function expandToolDetails(label: string) {
  const expand = await screen.findByRole('button', {
    name: `Show ${label} details`
  });
  fireEvent.click(expand);
  await waitFor(() => {
    expect(screen.getByRole('button', { name: `Hide ${label} details` })).toHaveAttribute(
      'aria-expanded',
      'true'
    );
  });
}

async function expandAllActivityDetails() {
  await waitFor(() => {
    expect(document.querySelector('.cr-task-turn-summary')).toBeTruthy();
  });
  for (const summary of document.querySelectorAll<HTMLButtonElement>('.cr-task-turn-summary')) {
    if (summary.getAttribute('aria-expanded') !== 'true') {
      fireEvent.click(summary);
    }
  }
  await waitFor(() => {
    expect(document.querySelector('.cr-run-step-button')).toBeTruthy();
  });
  for (const step of document.querySelectorAll<HTMLButtonElement>('.cr-run-step-button')) {
    if (step.getAttribute('aria-expanded') !== 'true') {
      fireEvent.click(step);
    }
  }
}

describe('AIAssistantPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders confirmation cards from assistant events', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c1","state":"thinking"}',
            'event: assistant.confirmation_requested\ndata: {"approval_id":"approval-1","tool_name":"create_project","arguments":{"name":"Acme Bid","scenario_package":"bidpilot"},"message":"需要你确认：我将创建项目「Acme Bid」。","state":"needs_confirmation"}',
            'event: assistant.message\ndata: {"content":"需要你确认：我将创建项目「Acme Bid」。","state":"needs_confirmation"}',
            'event: assistant.end\ndata: {"conversation_id":"c1","full_response":"需要你确认：我将创建项目「Acme Bid」。","state":"needs_confirmation"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Create a project named Acme Bid' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getByText('Confirm action')).toBeInTheDocument();
    });
    expect(screen.getAllByText('create_project').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Acme Bid/).length).toBeGreaterThan(0);
  });

  it('keeps the Linear composer focus state restrained', () => {
    render(
      <AIAssistantProvider>
        <AIAssistantPanel variant='linear-agent' />
      </AIAssistantProvider>
    );

    const textarea = screen.getByRole('textbox', { name: 'Ask me anything...' });
    expect(textarea).toHaveClass('focus-visible:ring-0', 'focus-visible:ring-offset-0');
    expect(screen.getByTestId('linear-agent-composer')).not.toHaveClass('focus-within:ring-2');
  });

  it('keeps an approval pause actionable when the SSE closes without assistant.end', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-approval","runtime_run_id":"run-approval","state":"thinking"}',
            'event: assistant.confirmation_requested\ndata: {"runtime_run_id":"run-approval","approval_id":"approval-1","tool_name":"fetch_url_to_project","arguments":{"url":"https://example.com/tender.doc"},"message":"确认把远程资料加入项目资料包。","state":"needs_confirmation"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Find tender attachments' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('Confirm action')).toBeInTheDocument();
    expect(screen.getByText('fetch_url_to_project')).toBeInTheDocument();
    expect(
      screen.queryByText(
        '助手连接已结束，但运行记录未报告终态。已解除待发送队列，请重试或查看运行记录。'
      )
    ).not.toBeInTheDocument();
  });

  it('keeps a missing-input pause actionable when a generic stream end follows it', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-input","runtime_run_id":"run-input","state":"thinking"}',
            'event: assistant.missing_input\ndata: {"runtime_run_id":"run-input","tool_name":"create_project","missing_fields":["name"],"message":"请提供项目名称。","state":"needs_input"}',
            'event: assistant.end\ndata: {"conversation_id":"c-input","full_response":"请提供项目名称。","state":"needs_input"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: '创建一个项目' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('需要补充信息')).toBeInTheDocument();
    expect(screen.getByText('请提供项目名称。')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('填写项目名称')).toBeInTheDocument();
    expect(screen.queryByText('本轮已完成')).not.toBeInTheDocument();
  });

  it('keeps Pi session lifecycle private instead of rendering timeline cards', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-pi-state","state":"thinking"}',
            'event: assistant.runtime_state\ndata: {"phase":"compaction.started","state":"thinking"}',
            'event: assistant.runtime_state\ndata: {"phase":"retry.started","attempt":1,"max_attempts":2,"state":"thinking"}',
            'event: assistant.message\ndata: {"content":"已恢复并完成。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c-pi-state","full_response":"已恢复并完成。"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: '继续处理' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('已恢复并完成。')).toBeInTheDocument();
    expect(screen.queryByText('compaction.started')).not.toBeInTheDocument();
    expect(screen.queryByText('retry.started')).not.toBeInTheDocument();
    expect(document.querySelector('.cr-task-turn-summary')).not.toBeInTheDocument();
  });

  it('shows the thinking indicator only after Pi reports a live thinking boundary', async () => {
    let controller: ReadableStreamDefaultController<Uint8Array> | null = null;
    const encoder = new TextEncoder();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: new ReadableStream({
          start(streamController) {
            controller = streamController;
          }
        })
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Live thinking check' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => expect(controller).not.toBeNull());
    controller!.enqueue(
      encoder.encode(
        [
          'event: assistant.start\ndata: {"conversation_id":"c-live-thinking","state":"thinking"}',
          'event: assistant.turn_started\ndata: {"turn_id":"turn-1","state":"thinking"}'
        ].join('\n\n') + '\n\n'
      )
    );
    expect(screen.queryByTestId('assistant-thinking-indicator')).not.toBeInTheDocument();
    expect(screen.getByTestId('assistant-waiting-indicator')).toBeInTheDocument();

    controller!.enqueue(
      encoder.encode(
        'event: assistant.runtime_state\ndata: {"phase":"thinking.started","state":"thinking"}\n\n'
      )
    );
    await waitFor(() => {
      expect(screen.getByTestId('assistant-thinking-indicator')).toBeInTheDocument();
    });
    expect(
      screen
        .getByTestId('assistant-thinking-indicator')
        .querySelector('.assistant-thinking-indicator__label')
    ).toHaveClass('assistant-thinking-indicator__label');

    controller!.enqueue(
      encoder.encode(
        'event: assistant.runtime_state\ndata: {"phase":"thinking.completed","state":"thinking"}\n\n'
      )
    );
    await waitFor(() => {
      expect(screen.queryByTestId('assistant-thinking-indicator')).not.toBeInTheDocument();
    });
    controller!.close();
  });

  it('submits a prompt once when Enter is pressed', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: streamFrom(
        [
          'event: assistant.start\\ndata: {"conversation_id":"enter-once","state":"thinking"}',
          'event: assistant.message\\ndata: {"content":"Hello back","state":"completed"}',
          'event: assistant.end\\ndata: {"conversation_id":"enter-once","full_response":"Hello back"}'
        ].join('\\n\\n') + '\\n\\n'
      )
    });
    vi.stubGlobal('fetch', fetchMock);

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    const input = screen.getByPlaceholderText('Ask me anything...');
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
  });

  it('turns send into a stop control and aborts the active response stream', async () => {
    let requestSignal: AbortSignal | undefined;
    const encoder = new TextEncoder();
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      requestSignal = init?.signal ?? undefined;
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            encoder.encode(
              'event: assistant.start\ndata: {"conversation_id":"c-stop","state":"thinking"}\n\n'
            )
          );
          requestSignal?.addEventListener('abort', () => {
            controller.error(Object.assign(new Error('Aborted'), { name: 'AbortError' }));
          });
        }
      });
      return Promise.resolve({ ok: true, body });
    });
    vi.stubGlobal('fetch', fetchMock);

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Long-running request' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    const stopButton = await screen.findByRole('button', {
      name: 'Stop generating'
    });
    fireEvent.click(stopButton);

    await waitFor(() => {
      expect(requestSignal?.aborted).toBe(true);
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument();
    });
    expect(screen.queryByText('Aborted')).not.toBeInTheDocument();
  });

  it('requests durable Pi cancellation and keeps the stop control locked until terminal state', async () => {
    const { cancelRuntimeWorkflow } = await import('@/lib/api');
    vi.mocked(cancelRuntimeWorkflow).mockResolvedValue({
      id: 'assistant-runtime-1',
      kind: 'assistant_turn',
      status: 'cancel_requested',
      project_id: null,
      conversation_id: 'c-runtime-stop',
      execution_run_id: null,
      engine: 'pi',
      trace_id: 'trace-runtime-stop',
      parent_run_id: null
    });
    const encoder = new TextEncoder();
    let streamController: ReadableStreamDefaultController<Uint8Array> | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: new ReadableStream<Uint8Array>({
          start(controller) {
            streamController = controller;
            controller.enqueue(
              encoder.encode(
                'event: assistant.start\ndata: {"conversation_id":"c-runtime-stop","runtime_run_id":"assistant-runtime-1","state":"thinking"}\n\n'
              )
            );
          }
        })
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Long-running Pi request' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    fireEvent.click(await screen.findByRole('button', { name: 'Stop generating' }));
    await waitFor(() => {
      expect(cancelRuntimeWorkflow).toHaveBeenCalledWith('assistant-runtime-1');
    });
    expect(screen.getByRole('button', { name: 'Stopping' })).toBeDisabled();

    streamController?.enqueue(
      encoder.encode(
        'event: assistant.end\ndata: {"conversation_id":"c-runtime-stop","runtime_run_id":"assistant-runtime-1","state":"completed"}\n\n'
      )
    );
    streamController?.close();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument();
    });
  });

  it('keeps a live tool run collapsed until the reader opens it', async () => {
    let requestSignal: AbortSignal | undefined;
    const encoder = new TextEncoder();
    vi.stubGlobal(
      'fetch',
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        requestSignal = init?.signal ?? undefined;
        const body = new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(
              encoder.encode(
                [
                  'event: assistant.start\ndata: {"conversation_id":"c-live","state":"thinking"}',
                  'event: assistant.tool_started\ndata: {"tool_name":"search_projects","tool_call_id":"call-live","arguments":{"query":"active"},"state":"executing_tool"}'
                ].join('\n\n') + '\n\n'
              )
            );
            requestSignal?.addEventListener('abort', () => {
              controller.error(Object.assign(new Error('Aborted'), { name: 'AbortError' }));
            });
          }
        });
        return Promise.resolve({ ok: true, body });
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Search active projects' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    const timeline = await screen.findByTestId('assistant-activity-timeline');
    expect(timeline).toHaveAttribute('data-status', 'running');
    expect(screen.getByTestId('assistant-activity-step-call-live')).toHaveAttribute(
      'data-status',
      'running'
    );
    const collapsedLiveTool = screen.getByRole('button', {
      name: 'Show Search projects details'
    });
    expect(collapsedLiveTool).toHaveAttribute('aria-busy', 'true');
    expect(collapsedLiveTool).toHaveAttribute('aria-expanded', 'false');
    expect(timeline.querySelector('.cr-live-label')).toBeTruthy();

    await expandActivityDetails();
    await expandToolDetails('Search projects');
    expect(screen.getByRole('button', { name: 'Hide Search projects details' })).toHaveAttribute(
      'aria-busy',
      'true'
    );

    fireEvent.click(screen.getByRole('button', { name: 'Stop generating' }));
    await waitFor(() => {
      expect(requestSignal?.aborted).toBe(true);
    });
  });

  it('merges a durable tool result into the live card when replay omits the call id', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-merge-tool","runtime_run_id":"run-merge-tool","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"runtime_run_id":"run-merge-tool","tool_name":"search_projects","tool_call_id":"call-live","state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"runtime_run_id":"run-merge-tool","tool_name":"search_projects","summary":"已完成项目检索。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c-merge-tool","runtime_run_id":"run-merge-tool","state":"completed"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Merge the durable tool result' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getByTestId('assistant-activity-step-call-live')).toHaveAttribute(
        'data-status',
        'succeeded'
      );
    });
    expect(screen.getAllByTestId('assistant-activity-step-call-live')).toHaveLength(1);
  });

  it('replays missed durable tool frames after a live terminal frame', async () => {
    const { listRuntimeEvents } = await import('@/lib/api');
    vi.mocked(listRuntimeEvents).mockResolvedValue({
      items: [
        {
          event_id: 'event-tool-started',
          run_id: 'run-live-terminal',
          parent_event_id: null,
          sequence: 2,
          type: 'capability.started',
          public_summary: '正在搜索项目。',
          payload: {
            capability: 'search_projects',
            tool_call_id: 'call-live-terminal',
            turn_id: 'turn-1',
            title: '搜索项目'
          },
          schema_version: '1.2',
          timestamp: '2026-08-29T00:00:02Z'
        },
        {
          event_id: 'event-tool-succeeded',
          run_id: 'run-live-terminal',
          parent_event_id: null,
          sequence: 3,
          type: 'capability.succeeded',
          public_summary: '找到 0 个项目。',
          payload: {
            capability: 'search_projects',
            tool_call_id: 'call-live-terminal',
            turn_id: 'turn-1',
            count: 0
          },
          schema_version: '1.2',
          timestamp: '2026-08-29T00:00:03Z'
        },
        {
          event_id: 'event-run-completed',
          run_id: 'run-live-terminal',
          parent_event_id: null,
          sequence: 4,
          type: 'run.completed',
          public_summary: '任务已完成。',
          payload: { status: 'succeeded', state: 'completed', kind: 'assistant_turn' },
          schema_version: '1.2',
          timestamp: '2026-08-29T00:00:04Z'
        }
      ]
    });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-live-terminal","runtime_run_id":"run-live-terminal","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"runtime_run_id":"run-live-terminal","tool_name":"search_projects","tool_call_id":"call-live-terminal","state":"executing_tool"}',
            'event: assistant.end\ndata: {"conversation_id":"c-live-terminal","runtime_run_id":"run-live-terminal","runtime_sequence":4,"state":"completed"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Replay the missed tool result' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getByTestId('assistant-activity-step-call-live-terminal')).toHaveAttribute(
        'data-status',
        'succeeded'
      );
    });
    expect(listRuntimeEvents).toHaveBeenCalledWith('run-live-terminal', 0);
  });

  it('surfaces a failed tool row when the stream ends without a tool result', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-no-ghost","runtime_run_id":"run-no-ghost","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"runtime_run_id":"run-no-ghost","tool_name":"search_projects","tool_call_id":"call-no-ghost","state":"executing_tool"}',
            'event: assistant.end\ndata: {"conversation_id":"c-no-ghost","runtime_run_id":"run-no-ghost","state":"failed"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'No ghost tool' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument());
    expect(screen.getByTestId('assistant-activity-step-call-no-ghost')).toHaveAttribute(
      'data-status',
      'failed'
    );
  });

  it('keeps separate Pi tool calls separate when the same capability runs twice', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-same-tool","runtime_run_id":"run-same-tool","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"runtime_run_id":"run-same-tool","tool_name":"search_projects","tool_call_id":"call-a","state":"executing_tool"}',
            'event: assistant.tool_started\ndata: {"runtime_run_id":"run-same-tool","tool_name":"search_projects","tool_call_id":"call-b","state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"runtime_run_id":"run-same-tool","tool_name":"search_projects","tool_call_id":"call-a","summary":"第一项已完成。","state":"completed"}',
            'event: assistant.tool_succeeded\ndata: {"runtime_run_id":"run-same-tool","tool_name":"search_projects","tool_call_id":"call-b","summary":"第二项已完成。","state":"completed"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Run the same read twice' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getByTestId('assistant-activity-step-call-a')).toHaveAttribute(
        'data-status',
        'succeeded'
      );
      expect(screen.getByTestId('assistant-activity-step-call-b')).toHaveAttribute(
        'data-status',
        'succeeded'
      );
    });
    expect(screen.getAllByTestId('assistant-activity-step-call-a')).toHaveLength(1);
    expect(screen.getAllByTestId('assistant-activity-step-call-b')).toHaveLength(1);
  });

  it('renders the workspace variant without opening the side panel', async () => {
    render(
      <AIAssistantProvider>
        <AIAssistantPanel variant='workspace' />
      </AIAssistantProvider>
    );

    expect(await screen.findByText('Welcome to BidPilot!')).toBeInTheDocument();
    const composer = screen.getByTestId('assistant-composer');
    expect(composer).toContainElement(screen.getByRole('textbox', { name: 'Ask me anything...' }));
    expect(screen.getByTestId('assistant-conversation-pane')).toContainElement(composer);
  });

  it('keeps the conversation open after a governed project action succeeds', async () => {
    const navigate = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"demo-conversation","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"create_demo_workspace","state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"create_demo_workspace","result":{"id":"demo-project-id"},"summary":"演示工作区已准备好。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"demo-conversation","state":"completed"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    render(
      <AIAssistantProvider navigate={navigate}>
        <OpenPanelButton />
        <AIAssistantPanel />
      </AIAssistantProvider>
    );
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Create a demo workspace' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(navigate).not.toHaveBeenCalled();
  });

  it('does not render intent trace cards in the default chat flow', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c2","state":"thinking"}',
            'event: assistant.intent_detected\ndata: {"mode":"answer","tool_name":"answer"}',
            'event: assistant.message\ndata: {"content":"这是直接回答。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c2","full_response":"这是直接回答。"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'What is this?' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getByText('这是直接回答。')).toBeInTheDocument();
    });
    expect(screen.queryByText('Intent: answer')).not.toBeInTheDocument();
    expect(screen.queryByText('Intent detected')).not.toBeInTheDocument();
  });

  it('keeps skill bootstrap events out of the user-facing activity timeline', async () => {
    const { listRuntimeEvents, listRuntimeRuns } = await import('@/lib/api');
    vi.mocked(listRuntimeRuns).mockResolvedValue({ items: [], next_cursor: null });
    vi.mocked(listRuntimeEvents).mockResolvedValue({ items: [] });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-skill","runtime_run_id":"r-skill","state":"thinking"}',
            'event: assistant.task_started\ndata: {"runtime_run_id":"r-skill","skill_name":"deep-research","title":"深度调研","turn_id":"turn-1","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"runtime_run_id":"r-skill","tool_name":"read_skill","resource_kind":"skill","resource_name":"deep-research","state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"runtime_run_id":"r-skill","tool_name":"read_skill","resource_kind":"skill","resource_name":"deep-research","summary":"已载入流程技能。","state":"completed"}',
            'event: assistant.message\ndata: {"runtime_run_id":"r-skill","content":"实际业务结果已准备好。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c-skill","runtime_run_id":"r-skill","state":"completed"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Check the project' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getByText('实际业务结果已准备好。')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('assistant-activity-timeline')).not.toBeInTheDocument();
  });

  it('replays durable runtime events after an assistant stream is interrupted', async () => {
    const { listRuntimeEvents } = await import('@/lib/api');
    vi.mocked(listRuntimeEvents).mockResolvedValue({
      items: [
        {
          event_id: 'event-runtime-replay-3',
          run_id: 'runtime-replay-1',
          parent_event_id: null,
          sequence: 3,
          type: 'capability.succeeded',
          public_summary: '找到 2 个项目。',
          payload: { capability: 'search_projects', count: 2 },
          schema_version: '1.0',
          timestamp: '2026-08-14T09:00:03Z'
        },
        {
          event_id: 'event-runtime-replay-4',
          run_id: 'runtime-replay-1',
          parent_event_id: null,
          sequence: 4,
          type: 'message.completed',
          public_summary: '当前共有 2 个项目。',
          payload: {},
          schema_version: '1.0',
          timestamp: '2026-08-14T09:00:04Z'
        },
        {
          event_id: 'event-runtime-replay-5',
          run_id: 'runtime-replay-1',
          parent_event_id: null,
          sequence: 5,
          type: 'run.completed',
          public_summary: '任务已完成。',
          payload: {},
          schema_version: '1.0',
          timestamp: '2026-08-14T09:00:05Z'
        }
      ]
    });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-replay","runtime_run_id":"runtime-replay-1","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"runtime_run_id":"runtime-replay-1","runtime_sequence":2,"tool_name":"search_projects","state":"executing_tool"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Show my projects' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(listRuntimeEvents).toHaveBeenCalledWith('runtime-replay-1', 2);
    });
    expect(screen.getByText('当前共有 2 个项目。')).toBeInTheDocument();
    expect(screen.queryByText('stream interrupted')).not.toBeInTheDocument();
  });

  it('accepts assistant.end when it shares a durable sequence with a failure frame', async () => {
    const { listRuntimeEvents } = await import('@/lib/api');
    vi.mocked(listRuntimeEvents).mockResolvedValue({ items: [] });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-terminal-sequence","runtime_run_id":"run-terminal-sequence","state":"thinking"}',
            'event: assistant.tool_failed\ndata: {"runtime_run_id":"run-terminal-sequence","runtime_sequence":14,"tool_name":"create_project","error_code":"project_limit_exceeded","error_message":"当前工作区已达到项目数量上限。","state":"failed"}',
            'event: assistant.end\ndata: {"conversation_id":"c-terminal-sequence","runtime_run_id":"run-terminal-sequence","runtime_sequence":14,"state":"failed"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Create a project' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(listRuntimeEvents).not.toHaveBeenCalledWith('run-terminal-sequence', 14);
    expect(screen.queryByText(/助手连接已结束/)).not.toBeInTheDocument();
  });

  it('keeps a queued prompt recoverable when an SSE response closes without a terminal event', async () => {
    const { listRuntimeEvents } = await import('@/lib/api');
    vi.mocked(listRuntimeEvents).mockResolvedValue({ items: [] });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          'event: assistant.start\ndata: {"conversation_id":"c-incomplete","runtime_run_id":"run-incomplete","state":"queued"}\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Show my projects' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(screen.queryByText(/助手连接已结束/)).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument());
  });

  it('keeps the composer editable while the assistant is responding', async () => {
    const fetchMock = vi.fn().mockImplementation(
      () =>
        new Promise(() => {
          // Keep the request open so the assistant remains busy.
        })
    );
    vi.stubGlobal('fetch', fetchMock);

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));

    const input = screen.getByPlaceholderText('Ask me anything...');
    fireEvent.change(input, { target: { value: 'Tell me the status' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    expect(screen.getByPlaceholderText('Ask me anything...')).not.toBeDisabled();
  });

  it('clears an unavailable selected provider without silently retrying on the platform model', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        text: vi.fn().mockResolvedValue(JSON.stringify({ detail: 'Provider config not found' }))
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Show my projects' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(
      await screen.findByText('所选模型配置已不可用，已切回平台默认模型。请确认后重新发送。')
    ).toBeInTheDocument();
    expect(document.querySelector('.cr-task-turn-summary')).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('requests cancellation only for a workflow that exposes its runtime bridge id', async () => {
    const { cancelRuntimeWorkflow, listRuntimeEvents } = await import('@/lib/api');
    vi.mocked(cancelRuntimeWorkflow).mockResolvedValue({
      id: 'workflow-runtime-1',
      kind: 'workflow_bridge',
      status: 'cancel_requested',
      project_id: 'project-1',
      conversation_id: 'conversation-1',
      execution_run_id: 'execution-run-1',
      engine: 'langgraph_workflow',
      trace_id: 'trace-1',
      parent_run_id: null
    });
    vi.mocked(listRuntimeEvents).mockImplementation(
      () =>
        new Promise(() => {
          // Keep the durable workflow live while the cancellation affordance is exercised.
        })
    );
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"conversation-1","state":"thinking"}',
            'event: assistant.workflow_started\ndata: {"tool_name":"start_draft_section","result":{"run_id":"execution-run-1","runtime_run_id":"workflow-runtime-1"},"state":"running_workflow"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Generate the technical approach' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await expandAllActivityDetails();
    const cancelButton = await screen.findByRole('button', {
      name: 'Cancel workflow'
    });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(cancelRuntimeWorkflow).toHaveBeenCalledWith('workflow-runtime-1');
    });
    expect(
      screen.getByText('Cancellation requested. Stopping at a safe boundary.')
    ).toBeInTheDocument();
  });

  it('shows a safe provider recovery action when a workflow fails', async () => {
    const { listRuntimeEvents } = await import('@/lib/api');
    vi.mocked(listRuntimeEvents).mockResolvedValue({
      items: [
        {
          event_id: 'event-provider-error-1',
          run_id: 'workflow-provider-error',
          parent_event_id: null,
          sequence: 1,
          type: 'capability.progressed',
          public_summary: '模型服务暂时不可用，正在重试。',
          payload: {
            capability: 'start_draft_section',
            node: 'section_drafter',
            phase: 'provider_retry',
            error_code: 'provider_rate_limited',
            next_attempt: 2,
            max_attempts: 3
          },
          schema_version: '1.0',
          timestamp: '2026-08-14T09:01:01Z'
        },
        {
          event_id: 'event-provider-error-2',
          run_id: 'workflow-provider-error',
          parent_event_id: null,
          sequence: 2,
          type: 'run.failed',
          public_summary: 'Workflow step could not finish.',
          payload: {
            capability: 'start_draft_section',
            error_code: 'provider_auth_failed'
          },
          schema_version: '1.0',
          timestamp: '2026-08-14T09:01:02Z'
        }
      ]
    });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"conversation-provider-error","state":"thinking"}',
            'event: assistant.workflow_started\ndata: {"tool_name":"start_draft_section","result":{"run_id":"execution-provider-error","runtime_run_id":"workflow-provider-error"},"state":"running_workflow"}',
            'event: assistant.end\ndata: {"conversation_id":"conversation-provider-error","state":"completed"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Generate a technical approach' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await expandAllActivityDetails();
    expect(
      await screen.findByText(
        'Model service authentication failed. Check the key and permissions, then test the connection again.'
      )
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Open model settings' }));
    expect(window.location.pathname).toBe('/settings/providers');
    window.history.replaceState({}, '', '/');
  });

  it('opens an attachment menu from the composer', async () => {
    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));

    fireEvent.click(screen.getByRole('button', { name: 'Add attachment' }));

    expect(await screen.findByText('Upload file')).toBeInTheDocument();
    expect(screen.getByText('Upload image')).toBeInTheDocument();
    expect(screen.getByText('Add from project')).toBeInTheDocument();
  });

  it('sends selected model config and reasoning effort with assistant requests', async () => {
    const { listProviderConfigs } = await import('@/lib/api');
    vi.mocked(listProviderConfigs).mockResolvedValue({
      data: [
        {
          id: 'provider-1',
          user_id: 'u1',
          provider_type: 'openai',
          provider_id: 'openai',
          api_key: 'sk-****',
          api_url: 'https://api.example.com/v1',
          model: 'gpt-5.5',
          label: 'GPT-5.5',
          is_active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      ]
    });
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: streamFrom(
        [
          'event: assistant.start\ndata: {"conversation_id":"c-model","state":"thinking"}',
          'event: assistant.message\ndata: {"content":"ok","state":"completed"}',
          'event: assistant.end\ndata: {"conversation_id":"c-model","full_response":"ok"}'
        ].join('\n\n') + '\n\n'
      )
    });
    vi.stubGlobal('fetch', fetchMock);

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));

    fireEvent.click(await screen.findByRole('button', { name: 'Select model' }));
    fireEvent.click(await screen.findByText('GPT-5.5'));
    fireEvent.click(screen.getByRole('button', { name: 'Select reasoning effort' }));
    fireEvent.click(screen.getByText('extra'));
    fireEvent.click(screen.getByRole('button', { name: 'Select approval mode' }));
    fireEvent.click(screen.getByText('Request approval'));

    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Use my selected model' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const requestBody = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(requestBody.provider_config_id).toBe('provider-1');
    expect(requestBody.reasoning_effort).toBe('extra');
    expect(requestBody.approval_mode).toBe('request_approval');
  });

  it('closes history before opening the attachment menu', async () => {
    const { listChatConversations } = await import('@/lib/api');
    vi.mocked(listChatConversations).mockResolvedValue([
      {
        id: 'c-menu',
        project_id: null,
        title: 'Menu overlap check',
        created_at: new Date().toISOString()
      }
    ]);

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.click(screen.getByTitle('Conversation history'));

    expect(await screen.findByPlaceholderText('Search conversations...')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Add attachment' }));

    expect(screen.getByText('Upload file')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Search conversations...')).not.toBeInTheDocument();
  });

  it('renders completed tool activity as a compact expandable event', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c3","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"open_page","arguments":{"route":"/projects"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"open_page","result":{"route":"/projects"},"summary":"raw detail should be hidden until expanded","state":"completed"}',
            'event: assistant.message\ndata: {"content":"已打开项目页。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c3","full_response":"已打开项目页。"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Open projects' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getAllByText('已打开项目页。').length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText('Open page').length).toBeGreaterThan(0);
    expect(screen.getByTestId('assistant-activity-timeline')).toHaveAttribute(
      'data-status',
      'succeeded'
    );
    expect(
      screen.queryByText('raw detail should be hidden until expanded')
    ).not.toBeInTheDocument();
    await expandActivityDetails();
    await expandToolDetails('Open page');
    expect(screen.getByText('raw detail should be hidden until expanded')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Hide Open page details' })).toBeInTheDocument();
    expect(
      screen
        .getAllByText('Open page')
        .find((element) => Boolean(element.closest('.cr-run-step')))!
        .compareDocumentPosition(screen.getAllByText('已打开项目页。')[0]) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
  });

  it('keeps raw tool payloads out of the activity timeline', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c6","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"search_projects","arguments":{"query":"test"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"search_projects","result":{"projects":[{"id":"p1","name":"test"}],"count":1},"summary":"content=\'{\\"projects\\":[{\\"id\\":\\"p1\\"}]}\' name=\'search_projects\' tool_call_id=\'call_123\'","state":"completed"}',
            'event: assistant.message\ndata: {"content":"找到 1 个项目。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c6","full_response":"找到 1 个项目。"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Search test projects' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getByText('找到 1 个项目。')).toBeInTheDocument();
    });

    await expandActivityDetails();

    expect(screen.getAllByText('Search projects').length).toBeGreaterThan(0);
    expect(screen.queryByText('Returned 1 results')).not.toBeInTheDocument();
    expect(screen.queryByText('Input')).not.toBeInTheDocument();
    expect(screen.queryByText('Output')).not.toBeInTheDocument();
    expect(screen.queryByText(/tool_call_id/)).not.toBeInTheDocument();
    expect(screen.queryByText(/content='/)).not.toBeInTheDocument();
  });

  it('renders platform tool names as user-facing labels', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-tools","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"get_project_summary","arguments":{"project_id":"p1"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"get_project_summary","result":{"name":"test","status":"active"},"summary":"项目 test 当前为 active。","state":"completed"}',
            'event: assistant.tool_started\ndata: {"tool_name":"list_project_bundles","arguments":{"project_id":"p1"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"list_project_bundles","result":{"bundles":[],"count":0},"summary":"暂无资料包。","state":"completed"}',
            'event: assistant.tool_started\ndata: {"tool_name":"list_deliverables","arguments":{"project_id":"p1"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"list_deliverables","result":{"deliverables":[],"count":0},"summary":"暂无交付物。","state":"completed"}',
            'event: assistant.tool_started\ndata: {"tool_name":"list_sections","arguments":{"project_id":"p1"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"list_sections","result":{"sections":[],"count":0},"summary":"暂无章节。","state":"completed"}',
            'event: assistant.message\ndata: {"content":"我查看了项目概况。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c-tools","full_response":"我查看了项目概况。"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: '查看项目状态' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getByText('我查看了项目概况。')).toBeInTheDocument();
    });

    await expandActivityDetails();

    expect(screen.getAllByText('Read project overview').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Check material bundles').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Check deliverables').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Check sections').length).toBeGreaterThan(0);
    expect(screen.queryByText('get_project_summary')).not.toBeInTheDocument();
    expect(screen.queryByText('list_project_bundles')).not.toBeInTheDocument();
    expect(screen.queryByText('list_deliverables')).not.toBeInTheDocument();
    expect(screen.queryByText('list_sections')).not.toBeInTheDocument();
  });

  it('makes discovered and imported remote materials visible as durable project work', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-remote","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"discover_remote_documents","tool_call_id":"discover-remote","state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"discover_remote_documents","tool_call_id":"discover-remote","result":{"count":2,"items":[{"filename":"招标文件.pdf","title":"采购文件","url":"https://buyer.example.test/files/rfp.pdf","content_type_hint":"application/pdf"},{"filename":"技术附件.docx","title":"技术附件","url":"https://buyer.example.test/files/appendix.docx","content_type_hint":"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}]},"summary":"发现 2 个附件，尚未下载。","state":"completed"}',
            'event: assistant.tool_started\ndata: {"tool_name":"fetch_url_to_project","tool_call_id":"import-remote","state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"fetch_url_to_project","tool_call_id":"import-remote","result":{"project_id":"project-1","bundle_id":"bundle-1","bundle_label":"招标附件","document_id":"doc-remote-1","filename":"招标文件.pdf","source_url":"https://buyer.example.test/files/rfp.pdf","parse_status":"pending","ingest_queued":true},"summary":"已加入项目资料包。","state":"completed"}',
            'event: assistant.message\ndata: {"content":"已完成远程资料入库。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c-remote","full_response":"已完成远程资料入库。"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: '收集招标附件' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getByText('已完成远程资料入库。')).toBeInTheDocument();
    });
    await expandActivityDetails();

    const discoveryStep = screen.getByTestId('assistant-activity-step-discover-remote');
    fireEvent.click(within(discoveryStep).getByRole('button'));
    expect(await screen.findByText('发现 2 个可入库附件')).toBeInTheDocument();
    expect(screen.getByText('招标文件.pdf')).toBeInTheDocument();
    expect(screen.getByText('技术附件.docx')).toBeInTheDocument();
    expect(screen.getByText('尚未下载')).toBeInTheDocument();

    const importStep = screen.getByTestId('assistant-activity-step-import-remote');
    fireEvent.click(within(importStep).getByRole('button'));
    expect(await screen.findByText('已加入项目资料包')).toBeInTheDocument();
    expect(screen.getByText('资料包：招标附件')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '查看资料中心' })).toHaveAttribute(
      'href',
      '/knowledge'
    );
    expect(screen.getByRole('link', { name: '原始公开来源' })).toHaveAttribute(
      'href',
      'https://buyer.example.test/files/rfp.pdf'
    );
    expect(screen.queryByText('doc-remote-1')).not.toBeInTheDocument();
  });

  it('keeps a large remote artifact visible while its background import is running', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-remote-queued","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"fetch_url_to_project","tool_call_id":"import-remote-queued","state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"fetch_url_to_project","tool_call_id":"import-remote-queued","result":{"status":"queued","runtime_run_id":"remote-import-run-1","project_id":"project-1","bundle_id":"bundle-1","source_url":"https://buyer.example.test/files/tender-software.zip","import_mode":"artifact"},"summary":"已开始后台下载远程资料。完成后会自动写入项目资料包；你可以继续使用当前对话。","state":"completed"}',
            'event: assistant.message\ndata: {"content":"已开始后台下载，完成后会自动入库。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c-remote-queued","full_response":"已开始后台下载，完成后会自动入库。"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: '下载投标软件附件' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getByText('已开始后台下载，完成后会自动入库。')).toBeInTheDocument();
    });
    await expandActivityDetails();

    const importStep = screen.getByTestId('assistant-activity-step-import-remote-queued');
    fireEvent.click(within(importStep).getByRole('button'));
    expect(await screen.findByText('后台导入已排队')).toBeInTheDocument();
    expect(screen.getByText('下载中，完成后自动入库')).toBeInTheDocument();
    expect(screen.getByText('远程资料下载任务')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '原始公开来源' })).toHaveAttribute(
      'href',
      'https://buyer.example.test/files/tender-software.zip'
    );
  });

  it('renders user attachments without leaking backend attachment context', async () => {
    const { uploadAssistantAttachment } = await import('@/lib/api');
    vi.mocked(uploadAssistantAttachment).mockResolvedValue({
      id: 'att-1',
      name: 'proposal.docx',
      kind: 'file',
      mime_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      size: 5,
      extraction_status: 'extracted',
      extracted_text: ''
    });
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: streamFrom(
        [
          'event: assistant.start\ndata: {"conversation_id":"c7","state":"thinking"}',
          'event: assistant.message\ndata: {"content":"我会参考这个文件。","state":"completed"}',
          'event: assistant.end\ndata: {"conversation_id":"c7","full_response":"我会参考这个文件。"}'
        ].join('\n\n') + '\n\n'
      )
    });
    vi.stubGlobal('fetch', fetchMock);

    const { container } = renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.click(screen.getByRole('button', { name: 'Add attachment' }));

    const fileInput = container.querySelector(
      'input[type="file"]:not([accept])'
    ) as HTMLInputElement;
    const file = new File(['hello'], 'proposal.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    });
    fireEvent.change(fileInput, { target: { files: [file] } });
    await waitFor(() => {
      expect(uploadAssistantAttachment).toHaveBeenCalledWith(file, 'file');
      expect(screen.getByText('proposal.docx')).toBeInTheDocument();
    });
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: '请分析这个文档' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    expect(screen.getByText('请分析这个文档')).toBeInTheDocument();
    expect(screen.queryByText(/附件上下文/)).not.toBeInTheDocument();
    const requestBody = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(requestBody.message).toBe('请分析这个文档');
    expect(requestBody.message).not.toContain('selected locally');
    expect(requestBody.attachments).toEqual([
      expect.objectContaining({
        id: 'att-1',
        name: 'proposal.docx',
        kind: 'file',
        extraction_status: 'extracted'
      })
    ]);
    expect(requestBody.attachments[0].extracted_text).toBe('');
  });

  it('keeps tool activity attached to the assistant turn that produced it', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c5","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"open_page","arguments":{"route":"/projects"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"open_page","result":{"route":"/projects"},"summary":"已打开项目页。","state":"completed"}',
            'event: assistant.message\ndata: {"content":"第一轮完成。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c5","full_response":"第一轮完成。"}'
          ].join('\n\n') + '\n\n'
        )
      })
      .mockResolvedValueOnce({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c5","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"search_projects","arguments":{"query":"Acme"},"state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"search_projects","result":{"count":1},"summary":"找到 1 个项目。","state":"completed"}',
            'event: assistant.message\ndata: {"content":"第二轮完成。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c5","full_response":"第二轮完成。"}'
          ].join('\n\n') + '\n\n'
        )
      });
    vi.stubGlobal('fetch', fetchMock);

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));

    const input = screen.getByPlaceholderText('Ask me anything...');
    fireEvent.change(input, { target: { value: 'Open projects' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getByText('第一轮完成。')).toBeInTheDocument();
      expect(screen.getAllByText('Open page').length).toBeGreaterThan(0);
    });

    fireEvent.change(input, { target: { value: 'Search Acme projects' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getByText('第二轮完成。')).toBeInTheDocument();
      expect(screen.getAllByText('Search projects').length).toBeGreaterThan(0);
    });

    const firstTool = screen.getAllByText('Open page')[0];
    const secondUserMessage = screen.getByText('Search Acme projects');
    expect(
      firstTool.compareDocumentPosition(secondUserMessage) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
  });

  it('renders assistant text immediately while the active tool trace is running', async () => {
    let controller: ReadableStreamDefaultController<Uint8Array> | null = null;
    const encoder = new TextEncoder();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: new ReadableStream({
          start(streamController) {
            controller = streamController;
          }
        })
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Search projects before answering' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(controller).not.toBeNull();
    });

    controller!.enqueue(
      encoder.encode(
        [
          'event: assistant.start\ndata: {"conversation_id":"c-buffer","state":"thinking"}',
          'event: assistant.tool_started\ndata: {"tool_name":"search_projects","tool_call_id":"call-1","arguments":{"query":"test"},"state":"executing_tool"}',
          'event: assistant.message\ndata: {"content":"找到 test 项目。","state":"thinking"}'
        ].join('\n\n') + '\n\n'
      )
    );

    await waitFor(() => {
      expect(screen.getByTestId('assistant-activity-timeline')).toHaveAttribute(
        'data-status',
        'running'
      );
      expect(screen.getByText('找到 test 项目。')).toBeInTheDocument();
    });

    controller!.enqueue(
      encoder.encode(
        [
          'event: assistant.tool_succeeded\ndata: {"tool_name":"search_projects","tool_call_id":"call-1","result":{"count":1},"summary":"找到 1 个项目。","state":"completed"}',
          'event: assistant.end\ndata: {"conversation_id":"c-buffer","full_response":"找到 test 项目。"}'
        ].join('\n\n') + '\n\n'
      )
    );
    controller!.close();

    await waitFor(() => {
      expect(screen.getAllByText('Search projects').length).toBeGreaterThan(0);
      expect(screen.getByText('找到 test 项目。')).toBeInTheDocument();
    });
  });

  it('supports renaming a conversation from history', async () => {
    const { listChatConversations, renameChatConversation } = await import('@/lib/api');
    vi.mocked(listChatConversations).mockResolvedValue([
      {
        id: 'c1',
        project_id: null,
        title: 'Old title',
        created_at: new Date().toISOString()
      }
    ]);
    vi.mocked(renameChatConversation).mockResolvedValue({
      id: 'c1',
      project_id: null,
      title: 'New title',
      created_at: new Date().toISOString()
    });

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));

    await waitFor(() => {
      expect(listChatConversations).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByTitle('Conversation history'));

    await waitFor(() => {
      expect(screen.getByText('Old title')).toBeInTheDocument();
    });

    fireEvent.doubleClick(screen.getByText('Old title'));

    const input = await screen.findByLabelText('Rename conversation');
    fireEvent.change(input, { target: { value: 'New title' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(renameChatConversation).toHaveBeenCalledWith('c1', 'New title');
    });
  });

  it('exposes a visible rename action for history conversations', async () => {
    const { listChatConversations, renameChatConversation } = await import('@/lib/api');
    vi.mocked(listChatConversations).mockResolvedValue([
      {
        id: 'c-visible-rename',
        project_id: null,
        title: 'Visible rename',
        created_at: new Date().toISOString()
      }
    ]);
    vi.mocked(renameChatConversation).mockResolvedValue({
      id: 'c-visible-rename',
      project_id: null,
      title: 'Renamed from button',
      created_at: new Date().toISOString()
    });

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.click(screen.getByTitle('Conversation history'));

    await screen.findByText('Visible rename');
    const row = screen.getByText('Visible rename').closest('[data-conversation-row]');
    expect(row).not.toBeNull();
    fireEvent.mouseEnter(row as HTMLElement);
    fireEvent.click(
      within(row as HTMLElement).getByRole('button', {
        name: 'Conversation actions'
      })
    );
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Rename conversation' }));

    const input = await screen.findByLabelText('Rename conversation');
    fireEvent.change(input, { target: { value: 'Renamed from button' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(renameChatConversation).toHaveBeenCalledWith(
        'c-visible-rename',
        'Renamed from button'
      );
    });
  });

  it('deletes a history conversation and refreshes the list', async () => {
    const { deleteChatConversation, listChatConversations } = await import('@/lib/api');
    vi.mocked(listChatConversations)
      .mockResolvedValueOnce([
        {
          id: 'c-delete',
          project_id: null,
          title: 'Delete me',
          created_at: new Date().toISOString()
        }
      ])
      .mockResolvedValueOnce([]);
    vi.mocked(deleteChatConversation).mockResolvedValue(undefined);

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.click(screen.getByTitle('Conversation history'));

    await screen.findByText('Delete me');
    const row = screen.getByText('Delete me').closest('[data-conversation-row]');
    expect(row).not.toBeNull();
    fireEvent.mouseEnter(row as HTMLElement);
    fireEvent.click(
      within(row as HTMLElement).getByRole('button', {
        name: 'Conversation actions'
      })
    );
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Delete conversation' }));

    await waitFor(() => {
      expect(deleteChatConversation).toHaveBeenCalledWith('c-delete');
      expect(listChatConversations).toHaveBeenCalledTimes(2);
    });
    expect(screen.queryByText('Delete me')).not.toBeInTheDocument();
  });

  it('switches the active conversation immediately while messages load', async () => {
    const { getChatConversationMessages, listChatConversations } = await import('@/lib/api');
    vi.mocked(listChatConversations).mockResolvedValue([
      {
        id: 'c-slow',
        project_id: null,
        title: 'Slow conversation',
        created_at: new Date().toISOString()
      }
    ]);
    vi.mocked(getChatConversationMessages).mockImplementation(
      () =>
        new Promise(() => {
          // Keep the request pending to prove the active title updates optimistically.
        })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.click(screen.getByTitle('Conversation history'));

    fireEvent.click(await screen.findByText('Slow conversation'));

    await waitFor(() => {
      expect(screen.getByText('Slow conversation')).toBeInTheDocument();
    });
    expect(screen.queryByPlaceholderText('Search conversations...')).not.toBeInTheDocument();
  });

  it('renders LangGraph workflow progress from run stream', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/assistant/stream')) {
        return Promise.resolve({
          ok: true,
          body: streamFrom(
            [
              'event: assistant.start\ndata: {"conversation_id":"c4","state":"thinking"}',
              'event: assistant.workflow_started\ndata: {"tool_name":"start_draft_section","arguments":{"section_key":"technical-approach"},"result":{"run_id":"run-1","status":"queued"},"state":"running_workflow"}',
              'event: assistant.tool_succeeded\ndata: {"tool_name":"start_draft_section","result":{"run_id":"run-1","status":"queued"},"summary":"已启动章节起草工作流，运行 ID：run-1。","state":"completed"}',
              'event: assistant.message\ndata: {"content":"已启动章节起草工作流，运行 ID：run-1。","state":"completed"}',
              'event: assistant.end\ndata: {"conversation_id":"c4","full_response":"已启动章节起草工作流，运行 ID：run-1。"}'
            ].join('\n\n') + '\n\n'
          )
        });
      }
      if (url.includes('/drafting/runs/run-1/stream')) {
        return Promise.resolve({
          ok: true,
          body: streamFrom(
            [
              'event: connected\ndata: {"run_id":"run-1","status":"running"}',
              'event: node_started\ndata: {"node_name":"section_drafter"}',
              'event: node_completed\ndata: {"node_name":"section_drafter","result_summary":"Draft created"}',
              'event: graph_completed\ndata: {"persisted":true,"status":"succeeded"}'
            ].join('\n\n') + '\n\n'
          )
        });
      }
      return Promise.resolve({ ok: true, body: streamFrom('') });
    });
    vi.stubGlobal('fetch', fetchMock);

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Draft technical section' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getAllByText('已启动章节起草工作流，运行 ID：run-1。').length).toBeGreaterThan(
        0
      );
    });
    await expandActivityDetails();
    await expandToolDetails('Start section draft');
    await waitFor(() => {
      expect(screen.getByText('Workflow steps')).toBeInTheDocument();
      expect(screen.getByText('Draft section')).toBeInTheDocument();
    });
    expect(screen.getByText('Workflow steps').closest('section')).toHaveTextContent('1/1');
  });

  it('offers authenticated downloads for Agent-generated artifacts', async () => {
    const { downloadAssistantArtifact } = await import('@/lib/api');
    vi.mocked(downloadAssistantArtifact).mockResolvedValue(undefined);
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          [
            'event: assistant.start\ndata: {"conversation_id":"c-download","state":"thinking"}',
            'event: assistant.tool_started\ndata: {"tool_name":"export_deliverable","state":"executing_tool"}',
            'event: assistant.tool_succeeded\ndata: {"tool_name":"export_deliverable","result":{"format":"docx","status":"ready","download_path":"/export/deliverables/123e4567-e89b-12d3-a456-426614174000/docx"},"summary":"交付物已生成，可下载。","state":"completed"}',
            'event: assistant.message\ndata: {"content":"交付物已生成，可下载。","state":"completed"}',
            'event: assistant.end\ndata: {"conversation_id":"c-download","full_response":"交付物已生成，可下载。"}'
          ].join('\n\n') + '\n\n'
        )
      })
    );

    renderPanel();
    fireEvent.click(screen.getByText('Open assistant'));
    fireEvent.change(screen.getByPlaceholderText('Ask me anything...'), {
      target: { value: 'Export the deliverable' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await expandActivityDetails();
    await expandToolDetails('Export deliverable');
    const downloadButton = await screen.findByRole('button', {
      name: 'Download DOCX'
    });
    fireEvent.click(downloadButton);
    await waitFor(() => {
      expect(downloadAssistantArtifact).toHaveBeenCalledWith(
        '/export/deliverables/123e4567-e89b-12d3-a456-426614174000/docx',
        'bidpilot-docx.docx'
      );
    });
  });
});
