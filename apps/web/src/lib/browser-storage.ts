export const STORAGE_KEYS = {
  token: "bidpilot_token",
  refreshToken: "bidpilot_refresh_token",
  language: "bidpilot_lang",
  guideDismissed: "bidpilot_guide_dismissed",
  onboardingDone: "bidpilot_onboarding_done",
  assistantProviderConfigId: "bidpilot_assistant_provider_config_id",
  assistantReasoningEffort: "bidpilot_assistant_reasoning_effort",
  assistantApprovalMode: "bidpilot_assistant_approval_mode",
  lastAssistantConversationId: "bidpilot_last_assistant_conversation_id",
} as const;

const LEGACY_PREFIX = [100, 111, 99, 112, 105, 108, 111, 116]
  .map((code) => String.fromCharCode(code))
  .join("");

const LEGACY_STORAGE_KEYS: Partial<Record<keyof typeof STORAGE_KEYS, string>> = {
  token: `${LEGACY_PREFIX}_token`,
  refreshToken: `${LEGACY_PREFIX}_refresh_token`,
  language: `${LEGACY_PREFIX}_lang`,
  guideDismissed: `${LEGACY_PREFIX}_guide_dismissed`,
  onboardingDone: `${LEGACY_PREFIX}_onboarding_done`,
};

type StorageKeyName = keyof typeof STORAGE_KEYS;

export function getStoredValue(key: StorageKeyName) {
  const value = localStorage.getItem(STORAGE_KEYS[key]);
  if (value !== null) return value;

  const legacyKey = LEGACY_STORAGE_KEYS[key];
  if (!legacyKey) return null;

  const legacyValue = localStorage.getItem(legacyKey);
  if (legacyValue !== null) {
    localStorage.setItem(STORAGE_KEYS[key], legacyValue);
    localStorage.removeItem(legacyKey);
  }
  return legacyValue;
}

export function setStoredValue(key: StorageKeyName, value: string) {
  localStorage.setItem(STORAGE_KEYS[key], value);
  const legacyKey = LEGACY_STORAGE_KEYS[key];
  if (legacyKey) localStorage.removeItem(legacyKey);
}

export function removeStoredValue(key: StorageKeyName) {
  localStorage.removeItem(STORAGE_KEYS[key]);
  const legacyKey = LEGACY_STORAGE_KEYS[key];
  if (legacyKey) localStorage.removeItem(legacyKey);
}
