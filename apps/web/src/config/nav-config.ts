import type { NavGroup } from '@/types';

export const navGroups: NavGroup[] = [
  {
    label: '工作台',
    items: [
      { title: '总览', url: '/dashboard', icon: 'dashboard', items: [] },
      { title: '项目', url: '/projects', icon: 'workspace', items: [] },
      { title: '助手', url: '/agent', icon: 'sparkles', items: [] }
    ]
  },
  {
    label: '投标工作流',
    items: [
      { title: '知识库', url: '/knowledge', icon: 'post', items: [] },
      { title: '需求清单', url: '/requirements', icon: 'forms', items: [] },
      { title: '运行记录', url: '/runs', icon: 'clock', items: [] },
      { title: '交付物', url: '/deliverables', icon: 'page', items: [] },
      { title: '评审', url: '/reviews', icon: 'badgeCheck', items: [] }
    ]
  },
  {
    label: '管理',
    items: [
      { title: '团队成员', url: '/members', icon: 'teams', items: [] },
      { title: '账户', url: '/account', icon: 'account', items: [] },
      { title: '设置', url: '/settings/providers', icon: 'settings', items: [] }
    ]
  }
];
