export type RegistrationErrorKey =
  | "toast.emailExists"
  | "toast.orgSlugExists"
  | "toast.passwordTooShort"
  | "toast.invitationInvalid"
  | "turnstile.failed"
  | "toast.registrationNetworkError"
  | "toast.registrationFailed";

function extractApiDetail(message: string) {
  const bodyStart = message.indexOf("{");
  if (bodyStart === -1) return message;

  try {
    const parsed = JSON.parse(message.slice(bodyStart)) as { detail?: unknown };
    return typeof parsed.detail === "string" ? parsed.detail : message;
  } catch {
    return message;
  }
}

export function getRegistrationErrorKey(error: unknown): RegistrationErrorKey {
  const rawMessage = error instanceof Error ? error.message : String(error);
  const detail = extractApiDetail(rawMessage);
  const message = detail.toLowerCase();

  if (message.includes("email already registered")) {
    return "toast.emailExists";
  }

  if (message.includes("organization with this slug")) {
    return "toast.orgSlugExists";
  }

  if (message.includes("password must")) {
    return "toast.passwordTooShort";
  }

  if (message.includes("invitation")) {
    return "toast.invitationInvalid";
  }

  if (message.includes("turnstile") || message.includes("human verification")) {
    return "turnstile.failed";
  }

  if (message.includes("failed to fetch") || message.includes("networkerror")) {
    return "toast.registrationNetworkError";
  }

  return "toast.registrationFailed";
}
