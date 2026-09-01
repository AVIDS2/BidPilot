import * as React from 'react';
import { useRouter } from 'next/navigation';
import { useTranslation } from 'react-i18next';
import { Command } from 'cmdk';
import {
  PlusIcon,
  UploadIcon,
  SparklesIcon,
  SearchIcon,
  DownloadIcon,
  BarChart3Icon,
  MessageCircleIcon,
  HelpCircleIcon,
  LayoutDashboardIcon,
  FileTextIcon,
  CreditCardIcon,
  SettingsIcon,
  UserIcon,
  MoonIcon,
  SunIcon,
  UsersIcon,
  BookOpenIcon,
  LightbulbIcon
} from 'lucide-react';
import { useTheme } from 'next-themes';
import { useAIAssistant } from '@/features/agent/state/agent-store';

type CommandPaletteProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();
  const navigate = React.useCallback((href: string) => router.push(href), [router]);
  const { t } = useTranslation();
  const { t: tAI } = useTranslation('ai-assistant');
  const { theme, setTheme } = useTheme();
  const { open: openAssistant, sendMessage } = useAIAssistant();

  const runAction = React.useCallback(
    (action: () => void) => {
      onOpenChange(false);
      action();
    },
    [onOpenChange]
  );

  if (!open) return null;

  return (
    <>
      {/* Overlay */}
      <button
        type='button'
        aria-label='关闭命令面板'
        className='fixed inset-0 z-50 bg-black/10 supports-backdrop-filter:backdrop-blur-xs'
        onClick={() => onOpenChange(false)}
      />

      {/* Dialog */}
      <div
        role='dialog'
        aria-modal='true'
        className='fixed top-[20%] left-1/2 z-50 w-full max-w-[calc(100%-2rem)] -translate-x-1/2 sm:max-w-lg'
      >
        <Command
          className='rounded-xl bg-popover text-popover-foreground ring-1 ring-foreground/10 shadow-lg overflow-hidden'
          onKeyDown={(e: React.KeyboardEvent) => {
            if (e.key === 'Escape') onOpenChange(false);
          }}
        >
          <div className='flex items-center border-b px-3'>
            <SearchIcon className='size-4 shrink-0 text-muted-foreground' />
            <Command.Input
              autoFocus
              placeholder={t('commandPalette.placeholder')}
              className='flex h-11 w-full rounded-md bg-transparent py-3 pl-2 pr-3 text-sm outline-none placeholder:text-muted-foreground'
            />
            <kbd className='pointer-events-none hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground sm:flex'>
              ESC
            </kbd>
          </div>

          <Command.List className='max-h-[360px] overflow-y-auto overflow-x-hidden p-1'>
            <Command.Empty className='py-6 text-center text-sm text-muted-foreground'>
              {t('commandPalette.noResults')}
            </Command.Empty>

            {/* ─── Navigation ─── */}
            <Command.Group
              heading={t('commandPalette.groups.navigation')}
              className='px-2 py-1.5 text-xs font-medium text-muted-foreground [&>[cmdk-group-heading]]:px-2 [&>[cmdk-group-heading]]:py-1.5'
            >
              <CmdItem
                icon={<LayoutDashboardIcon />}
                label={t('nav.dashboard')}
                shortcut='G D'
                onSelect={() => runAction(() => navigate('/dashboard'))}
              />
              <CmdItem
                icon={<FileTextIcon />}
                label={t('nav.projects')}
                shortcut='G P'
                onSelect={() => runAction(() => navigate('/projects'))}
              />
              <CmdItem
                icon={<CreditCardIcon />}
                label={t('nav.pricing')}
                onSelect={() => runAction(() => navigate('/pricing'))}
              />
              <CmdItem
                icon={<UserIcon />}
                label={t('nav.account')}
                onSelect={() => runAction(() => navigate('/account'))}
              />
              <CmdItem
                icon={<SettingsIcon />}
                label={t('nav.settings')}
                onSelect={() => runAction(() => navigate('/settings/providers'))}
              />
              <CmdItem
                icon={<UsersIcon />}
                label={t('nav.users')}
                onSelect={() => runAction(() => navigate('/admin/users'))}
              />
              <CmdItem
                icon={<BookOpenIcon />}
                label={t('nav.docs')}
                onSelect={() => runAction(() => navigate('/docs'))}
              />
            </Command.Group>

            <Command.Separator className='mx-2 my-1 h-px bg-border' />

            {/* ─── Actions ─── */}
            <Command.Group
              heading={t('commandPalette.groups.actions')}
              className='px-2 py-1.5 text-xs font-medium text-muted-foreground [&>[cmdk-group-heading]]:px-2 [&>[cmdk-group-heading]]:py-1.5'
            >
              <CmdItem
                icon={<PlusIcon />}
                label={tAI('commands.createProject')}
                shortcut='N'
                onSelect={() => runAction(() => navigate('/projects'))}
              />
              <CmdItem
                icon={<UploadIcon />}
                label={tAI('commands.uploadDoc')}
                onSelect={() =>
                  runAction(() => {
                    sendMessage(tAI('actions.uploadDocPrompt'));
                    openAssistant('panel');
                  })
                }
              />
              <CmdItem
                icon={<SparklesIcon />}
                label={tAI('commands.generateSection')}
                onSelect={() =>
                  runAction(() => {
                    sendMessage(tAI('actions.generateSectionPrompt'));
                    openAssistant('panel');
                  })
                }
              />
              <CmdItem
                icon={<SearchIcon />}
                label={tAI('commands.searchKnowledge')}
                onSelect={() =>
                  runAction(() => {
                    sendMessage(tAI('commands.searchKnowledge'));
                    openAssistant('panel');
                  })
                }
              />
              <CmdItem
                icon={<DownloadIcon />}
                label={tAI('commands.exportDoc')}
                onSelect={() => runAction(() => navigate('/projects'))}
              />
              <CmdItem
                icon={<BarChart3Icon />}
                label={tAI('commands.viewStatus')}
                onSelect={() => runAction(() => navigate('/dashboard'))}
              />
              <CmdItem
                icon={theme === 'dark' ? <SunIcon /> : <MoonIcon />}
                label={t('commandPalette.actions.toggleTheme')}
                onSelect={() => runAction(() => setTheme(theme === 'dark' ? 'light' : 'dark'))}
              />
            </Command.Group>

            <Command.Separator className='mx-2 my-1 h-px bg-border' />

            {/* ─── AI ─── */}
            <Command.Group
              heading={tAI('commands.groups.ai')}
              className='px-2 py-1.5 text-xs font-medium text-muted-foreground [&>[cmdk-group-heading]]:px-2 [&>[cmdk-group-heading]]:py-1.5'
            >
              <CmdItem
                icon={<MessageCircleIcon />}
                label={tAI('commands.aiChat')}
                shortcut='⌘⇧A'
                onSelect={() => runAction(() => openAssistant('panel'))}
              />
              <CmdItem
                icon={<LightbulbIcon />}
                label={tAI('commands.aiSuggest')}
                onSelect={() =>
                  runAction(() => {
                    sendMessage(tAI('commands.aiSuggestPrompt'));
                    openAssistant('panel');
                  })
                }
              />
              <CmdItem
                icon={<HelpCircleIcon />}
                label={tAI('commands.help')}
                onSelect={() =>
                  runAction(() => {
                    sendMessage(tAI('actions.howToUsePrompt'));
                    openAssistant('panel');
                  })
                }
              />
            </Command.Group>
          </Command.List>

          <div className='flex items-center justify-between border-t px-3 py-2 text-xs text-muted-foreground'>
            <span>{t('commandPalette.hint.navigate')}</span>
            <span>{t('commandPalette.hint.select')}</span>
          </div>
        </Command>
      </div>
    </>
  );
}

/* ─── Reusable command item ─── */

function CmdItem({
  icon,
  label,
  shortcut,
  onSelect
}: {
  icon: React.ReactNode;
  label: string;
  shortcut?: string;
  onSelect: () => void;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className='relative flex cursor-pointer select-none items-center gap-3 rounded-md px-2 py-2 text-sm outline-none aria-selected:bg-accent aria-selected:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50'
    >
      <span className='flex size-5 shrink-0 items-center justify-center text-muted-foreground [&>svg]:size-4'>
        {icon}
      </span>
      <span className='flex-1 truncate'>{label}</span>
      {shortcut && (
        <kbd className='pointer-events-none hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground sm:flex'>
          {shortcut}
        </kbd>
      )}
    </Command.Item>
  );
}
