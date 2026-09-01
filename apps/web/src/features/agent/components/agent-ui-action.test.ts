import { describe, expect, it } from 'vitest';
import { parseAgentUiAction } from './agent-ui-action';

describe('parseAgentUiAction', () => {
  it('accepts the allow-listed workflow canvas action', () => {
    expect(
      parseAgentUiAction({
        type: 'canvas',
        label: '打开响应工作流',
        route: '/projects/project-1?surface=workflow'
      })
    ).toEqual({
      type: 'canvas',
      label: '打开响应工作流',
      route: '/projects/project-1?surface=workflow',
      projectId: 'project-1'
    });
  });

  it('rejects arbitrary routes and executable links', () => {
    expect(parseAgentUiAction({ type: 'canvas', route: '/admin/users' })).toBeNull();
    expect(parseAgentUiAction({ type: 'link', href: 'javascript:alert(1)' })).toBeNull();
    expect(parseAgentUiAction({ type: 'link', href: '/projects/project-1' })).toBeNull();
  });

  it('accepts only http(s) external links', () => {
    expect(
      parseAgentUiAction({
        type: 'link',
        label: '查看公告',
        href: 'https://example.com/notice'
      })
    ).toEqual({
      type: 'external-link',
      label: '查看公告',
      href: 'https://example.com/notice'
    });
  });
});
