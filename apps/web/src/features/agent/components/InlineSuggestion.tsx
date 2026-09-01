import { usePathname } from 'next/navigation';
import { SparklesIcon, ArrowRightIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAIAssistant, type InlineSuggestion } from '@/features/agent/state/agent-store';
import { cn } from '@/lib/utils';

/* ─── Context-aware suggestion rules ─── */

type SuggestionRule = {
  /** regex tested against pathname */
  pattern: RegExp;
  /** build suggestions for this page */
  build: (
    t: (key: string) => string,
    sendMessage: (msg: string) => void,
    openPanel: () => void
  ) => InlineSuggestion[];
};

function usePageSuggestions(): InlineSuggestion[] {
  const pathname = usePathname();
  const { sendMessage, open } = useAIAssistant();
  const { t } = useTranslation('ai-assistant');

  const rules: SuggestionRule[] = [
    {
      pattern: /^\/projects$/,
      build: (t, send, openP) => [
        {
          id: 'create-new-project',
          text: t('suggestions.createProject'),
          action: () => {
            send(t('actions.createProjectPrompt'));
            openP();
          }
        },
        {
          id: 'project-tips',
          text: t('suggestions.projectTips'),
          action: () => {
            send(t('suggestions.projectTipsPrompt'));
            openP();
          }
        }
      ]
    },
    {
      pattern: /^\/projects\/[^/]+$/,
      build: (t, send, openP) => [
        {
          id: 'generate-section',
          text: t('suggestions.generateSection'),
          action: () => {
            send(t('actions.generateSectionPrompt'));
            openP();
          }
        },
        {
          id: 'upload-document',
          text: t('suggestions.uploadDocument'),
          action: () => {
            send(t('actions.uploadDocPrompt'));
            openP();
          }
        },
        {
          id: 'export-project',
          text: t('suggestions.exportProject'),
          action: () => {
            send(t('suggestions.exportProjectPrompt'));
            openP();
          }
        }
      ]
    },
    {
      pattern: /^\/dashboard$/,
      build: (t, send, openP) => [
        {
          id: 'view-overview',
          text: t('suggestions.dashboardOverview'),
          action: () => {
            send(t('suggestions.dashboardOverviewPrompt'));
            openP();
          }
        }
      ]
    },
    {
      pattern: /^\/admin\/users$/,
      build: (t, send, openP) => [
        {
          id: 'user-management-help',
          text: t('suggestions.userManagement'),
          action: () => {
            send(t('suggestions.userManagementPrompt'));
            openP();
          }
        }
      ]
    },
    {
      pattern: /^\/settings/,
      build: (t, send, openP) => [
        {
          id: 'provider-setup-help',
          text: t('suggestions.providerSetup'),
          action: () => {
            send(t('suggestions.providerSetupPrompt'));
            openP();
          }
        }
      ]
    }
  ];

  for (const rule of rules) {
    if (rule.pattern.test(pathname)) {
      return rule.build(
        (key) => t(key),
        sendMessage,
        () => open('panel')
      );
    }
  }
  return [];
}

/* ─── InlineSuggestion bar ─── */

/**
 * Renders context-aware suggestion chips below the site header.
 * Only shown when the assistant panel is closed and suggestions exist for the current page.
 */
export function InlineSuggestionBar() {
  const { state } = useAIAssistant();
  const suggestions = usePageSuggestions();

  if (suggestions.length === 0) return null;

  return (
    <div
      className='flex items-center gap-2 px-4 py-2 animate-fade-in transition-opacity duration-200'
      style={{
        borderBottom: '1px solid var(--border)',
        background: 'oklch(from var(--primary) l c h / 0.03)',
        opacity: state.isOpen ? 0.78 : 1
      }}
    >
      <SparklesIcon className='w-3.5 h-3.5 shrink-0' style={{ color: 'var(--primary)' }} />
      <div className='flex items-center gap-2 overflow-x-auto no-scrollbar'>
        {suggestions.map((s) => (
          <SuggestionChip key={s.id} suggestion={s} />
        ))}
      </div>
    </div>
  );
}

/* ─── Single chip ─── */

function SuggestionChip({ suggestion }: { suggestion: InlineSuggestion }) {
  return (
    <button
      onClick={suggestion.action}
      className={cn(
        'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs',
        'transition-all duration-200 hover:scale-105 whitespace-nowrap shrink-0'
      )}
      style={{
        background: 'var(--card)',
        border: '1px solid var(--border)',
        color: 'var(--foreground)'
      }}
    >
      {suggestion.text}
      <ArrowRightIcon className='w-3 h-3 opacity-50' />
    </button>
  );
}
