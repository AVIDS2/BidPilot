export type PiExtensionDeployment = "governed_cloud" | "isolated_workspace";

export interface TrustedPiExtensionDescriptor {
  id: string;
  version: number;
  deployment: PiExtensionDeployment;
  source: "first_party";
  hidden: boolean;
  purpose: string;
}

/**
 * Server-side admission list for executable Pi extensions.
 *
 * Pi packages execute arbitrary code in the host process. Cloud admission is
 * therefore a build-time decision, not a tenant setting or an npm package
 * name supplied at runtime.
 */
export const TRUSTED_PI_EXTENSIONS = {
  "bidpilot-governance": {
    id: "bidpilot-governance",
    version: 1,
    deployment: "governed_cloud",
    source: "first_party",
    hidden: true,
    purpose: "Recheck the API-authorized tool boundary at Pi's native tool hook.",
  },
  "bidpilot-skills": {
    id: "bidpilot-skills",
    version: 1,
    deployment: "governed_cloud",
    source: "first_party",
    hidden: true,
    purpose: "Expose the trusted progressive-disclosure Skill catalogue.",
  },
  "bidpilot-subagents": {
    id: "bidpilot-subagents",
    version: 1,
    deployment: "governed_cloud",
    source: "first_party",
    hidden: true,
    purpose: "Delegate bounded child work through the durable API control plane.",
  },
} as const satisfies Record<string, TrustedPiExtensionDescriptor>;

export type TrustedPiExtensionId = keyof typeof TRUSTED_PI_EXTENSIONS;

export function trustedCloudExtension(id: string): TrustedPiExtensionDescriptor | undefined {
  const descriptor = TRUSTED_PI_EXTENSIONS[id as TrustedPiExtensionId];
  return descriptor?.deployment === "governed_cloud" ? descriptor : undefined;
}
