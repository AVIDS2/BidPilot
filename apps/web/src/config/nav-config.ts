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
      { title: '交付物', url: '/deliverables', icon: 'page', items: [] },
      { title: '评审', url: '/reviews', icon: 'badgeCheck', items: [] }
    ]
  },
  {
    label: '工作流运营',
    items: [
      { title: '收件箱', url: '/inbox', icon: 'inbox', items: [] },
      { title: '我的工作', url: '/my-work', icon: 'myWork', items: [] },
      { title: '招采雷达', url: '/radar', icon: 'radar', items: [] }
    ]
  },
  {
    label: '工作区',
    items: [
      { title: '团队成员', url: '/members', icon: 'teams', items: [] },
      { title: '账户', url: '/account', icon: 'account', items: [] },
      { title: '设置', url: '/settings/providers', icon: 'settings', items: [] }
    ]
  },
  {
    label: '管理员',
    items: [
      {
        title: '工作区管理',
        url: '/administration',
        icon: 'settings',
        items: [],
        access: { role: 'admin' }
      },
      {
        title: '用户管理',
        url: '/admin/users',
        icon: 'teams',
        items: [],
        access: { role: 'admin' }
      },
      {
        title: '团队管理',
        url: '/admin/teams',
        icon: 'workspace',
        items: [],
        access: { role: 'admin' }
      },
      {
        title: '邀请管理',
        url: '/admin/invitations',
        icon: 'mail',
        items: [],
        access: { role: 'admin' }
      },
      {
        title: 'Webhook',
        url: '/settings/webhooks',
        icon: 'settings',
        items: [],
        access: { role: 'admin' }
      }
    ]
  }
];
