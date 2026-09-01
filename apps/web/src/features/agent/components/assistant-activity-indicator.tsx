import { useTranslation } from 'react-i18next';
import './assistant-activity-indicator.css';

export function AssistantActivityIndicator({ phase }: { phase: 'waiting' | 'thinking' }) {
  const { t } = useTranslation('ai-assistant');
  const label =
    phase === 'thinking'
      ? t('status.nativeThinking', { defaultValue: '正在思考' })
      : t('status.waiting', { defaultValue: '等待首个响应' });

  if (phase === 'thinking') {
    return (
      <span
        aria-label={label}
        className='inline-flex min-h-6 items-center text-sm text-muted-foreground'
        data-testid='assistant-thinking-indicator'
        role='status'
      >
        <span className='assistant-thinking-indicator__label'>{label}</span>
      </span>
    );
  }

  return (
    <span
      aria-label={label}
      className='inline-flex min-h-6 items-center gap-1.5 text-muted-foreground'
      data-testid='assistant-waiting-indicator'
      role='status'
    >
      <span className='size-1.5 animate-pulse rounded-full bg-current' />
      <span className='size-1.5 animate-pulse rounded-full bg-current [animation-delay:150ms]' />
      <span className='size-1.5 animate-pulse rounded-full bg-current [animation-delay:300ms]' />
    </span>
  );
}
