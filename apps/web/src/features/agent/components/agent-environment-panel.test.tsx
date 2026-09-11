import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { listRuntimeRuns } from '@/lib/api';
import { AgentEnvironmentPanel } from './agent-environment-panel';

vi.mock('@/lib/api', () => ({
  listProjects: vi.fn().mockResolvedValue([
    {
      id: 'p1',
      name: '常州项目',
      slug: 'changzhou',
      scenario_package: '招标响应',
      status: 'active'
    }
  ]),
  listRuntimeRuns: vi.fn().mockResolvedValue([
    {
      id: 'run-1',
      kind: 'subagent',
      status: 'running',
      project_id: 'p1',
      conversation_id: 'conversation-1',
      project_name: '常州项目',
      engine: 'pi_subagent_worker',
      created_at: '2026-08-25T12:00:00Z',
      started_at: '2026-08-25T12:00:00Z',
      finished_at: null,
      latest_event_summary: '正在核对官方来源'
    },
    {
      id: 'run-2',
      kind: 'deep_research',
      status: 'awaiting_approval',
      project_id: 'p1',
      conversation_id: 'conversation-1',
      project_name: '常州项目',
      engine: 'deep_research_worker',
      created_at: '2026-08-25T12:01:00Z',
      started_at: null,
      finished_at: null,
      latest_event_summary: '等待确认研究范围'
    }
  ])
}));

describe('AgentEnvironmentPanel', () => {
  it('renders live runs and the server-owned Pi resource contract', async () => {
    const onOpenRun = vi.fn();
    const onOpenSubagents = vi.fn();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <AgentEnvironmentPanel onOpenRun={onOpenRun} onOpenSubagents={onOpenSubagents} />
      </QueryClientProvider>
    );

    expect(await screen.findByText('工作概览')).toBeInTheDocument();
    expect(screen.getByText('进行中的任务')).toBeInTheDocument();
    expect(await screen.findByText('1 个协作助理正在工作')).toBeInTheDocument();
    expect(await screen.findByText('协作助理')).toBeInTheDocument();
    expect(await screen.findByText('深度调研')).toBeInTheDocument();
    expect(screen.getByText('项目工作区')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /协作助理/ }));
    expect(onOpenSubagents).toHaveBeenCalledWith('run-1');
    expect(onOpenRun).not.toHaveBeenCalled();
  });

  it('keeps assistant turns out of the background-work overview', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <AgentEnvironmentPanel onOpenRun={vi.fn()} />
      </QueryClientProvider>
    );

    await screen.findByText('工作概览');
    expect(screen.queryByText('助手会话')).not.toBeInTheDocument();
    expect(await screen.findByText('协作助理')).toBeInTheDocument();
  });

  it('does not turn a failed background query into a false empty state', async () => {
    vi.mocked(listRuntimeRuns).mockRejectedValueOnce(new Error('background unavailable'));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <AgentEnvironmentPanel onOpenRun={vi.fn()} />
      </QueryClientProvider>
    );

    expect(await screen.findByText('协作进度暂时无法读取。')).toBeInTheDocument();
    expect(screen.queryByText('目前没有协作事项')).not.toBeInTheDocument();
  });
});
