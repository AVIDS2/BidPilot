export interface RegistrationDraft {
  displayName: string;
  email: string;
  invitationToken: string;
  orgName: string;
  orgSlug: string;
}

const REGISTRATION_DRAFT_KEY = "bidpilot_registration_draft";

export function readRegistrationDraft(): RegistrationDraft | null {
  try {
    const raw = sessionStorage.getItem(REGISTRATION_DRAFT_KEY);
    if (!raw) return null;
    const draft = JSON.parse(raw) as Partial<RegistrationDraft>;
    if (typeof draft.email !== "string") return null;
    return {
      displayName: draft.displayName ?? "",
      email: draft.email,
      invitationToken: draft.invitationToken ?? "",
      orgName: draft.orgName ?? "",
      orgSlug: draft.orgSlug ?? "",
    };
  } catch {
    return null;
  }
}

export function saveRegistrationDraft(draft: RegistrationDraft) {
  sessionStorage.setItem(REGISTRATION_DRAFT_KEY, JSON.stringify(draft));
}

export function clearRegistrationDraft() {
  sessionStorage.removeItem(REGISTRATION_DRAFT_KEY);
}
