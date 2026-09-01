/**
 * Public boundary for the active Agent feature.
 *
 * Route and shell code should import the feature surface from here. Runtime
 * projection and client state stay private to the feature implementation.
 */
export { AgentWorkspacePage } from './agent-workspace-page';
export {
  AIAssistantPanel,
  AgentWakeResume,
  CommandPalette,
  FloatingAssistant,
  InlineSuggestionBar
} from './components';
export { AIAssistantProvider, isAssistantBusy, useAIAssistant } from './state/agent-store';
export type {
  AIAssistantState,
  AssistantExecutionItem,
  AssistantConfirmationRequest,
  AssistantInputRequest,
  AssistantReasoningEffort,
  AssistantApprovalMode,
  ChatMessage
} from './state/agent-store';
