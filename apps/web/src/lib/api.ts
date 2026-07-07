import { getStoredValue } from "@/lib/browser-storage";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function getAuthHeaders(): Record<string, string> {
  const token = getStoredValue("token");
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

// Rate limit retry configuration
const RETRY_CONFIG = {
  maxRetries: 3,
  baseDelay: 1000,
  maxDelay: 10000,
};

// Delay utility with exponential backoff
function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Check if error is rate limit (429)
function isRateLimitError(error: unknown): error is { status: number } {
  return (
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    (error as { status: number }).status === 429
  );
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let lastError: unknown;

  for (let attempt = 0; attempt <= RETRY_CONFIG.maxRetries; attempt++) {
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeaders(),
          ...options?.headers,
        },
        ...options,
      });

      if (res.status === 429) {
        // Rate limit exceeded - extract retry-after or use exponential backoff
        const retryAfter = res.headers.get("Retry-After");
        const retryMs = retryAfter
          ? parseInt(retryAfter, 10) * 1000
          : Math.min(
              RETRY_CONFIG.baseDelay * Math.pow(2, attempt),
              RETRY_CONFIG.maxDelay,
            );

        if (attempt < RETRY_CONFIG.maxRetries) {
          await delay(retryMs);
          continue; // Retry
        }
      }

      if (!res.ok) {
        const body = await res.text().catch(() => "");
        const error = new Error(`API ${res.status}: ${body}`) as Error & {
          status: number;
        };
        error.status = res.status;
        throw error;
      }

      if (res.status === 204) {
        return undefined as T;
      }

      const text = await res.text();
      if (!text) {
        return undefined as T;
      }

      return JSON.parse(text) as T;
    } catch (error) {
      lastError = error;

      // If it's a rate limit error and we haven't exhausted retries, wait and retry
      if (isRateLimitError(error) && attempt < RETRY_CONFIG.maxRetries) {
        const retryMs = Math.min(
          RETRY_CONFIG.baseDelay * Math.pow(2, attempt),
          RETRY_CONFIG.maxDelay,
        );
        await delay(retryMs);
        continue;
      }

      // For non-rate-limit errors or exhausted retries, throw immediately
      throw error;
    }
  }

  throw lastError;
}

async function requestBlob(path: string, options?: RequestInit): Promise<Blob> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { ...getAuthHeaders(), ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.blob();
}

// Project
export interface ProjectRead {
  id: string;
  slug: string;
  name: string;
  scenario_package: string;
  status: string;
  org_id?: string;
  org_slug?: string;
}

export function listProjects() {
  return request<ProjectRead[]>("/projects");
}

export function createProject(data: { name: string; scenario_package: string }) {
  return request<ProjectRead>("/projects", { method: "POST", body: JSON.stringify(data) });
}

export function getProject(id: string) {
  return request<ProjectRead>(`/projects/${id}`);
}

export function updateProjectStatus(id: string, status: string) {
  return request<ProjectRead>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
}

export function deleteProject(id: string) {
  return request<void>(`/projects/${id}`, { method: "DELETE" });
}

// Bundle
export interface BundleRead {
  id: string;
  project_id: string;
  label: string;
  source_type: string;
  ingest_status: string;
}

export function listBundles(projectId: string) {
  return request<BundleRead[]>(`/bundles?project_id=${projectId}`);
}

export function createBundle(data: { project_id: string; label: string; source_type: string }) {
  return request<BundleRead>("/bundles", { method: "POST", body: JSON.stringify(data) });
}

// Deliverable
export interface DeliverableRead {
  id: string;
  project_id: string;
  type: string;
  title: string;
  status: string;
  export_status: string;
}

export function listDeliverables(projectId: string) {
  return request<DeliverableRead[]>(`/deliverables?project_id=${projectId}`);
}

export function createDeliverable(data: { project_id: string; type: string; title: string }) {
  return request<DeliverableRead>("/deliverables", { method: "POST", body: JSON.stringify(data) });
}

// Deliverable Sections
export interface DeliverableSectionRead {
  id: string;
  deliverable_id: string;
  section_key: string;
  title: string;
  status: string;
  assignee_type: string;
}

export function listDeliverableSections(deliverableId: string) {
  return request<DeliverableSectionRead[]>(`/deliverables/${deliverableId}/sections`);
}

// Documents
export interface SourceDocumentRead {
  id: string;
  bundle_id: string;
  storage_key: string;
  mime_type: string;
  original_filename: string;
  parse_status: string;
}

export interface DocumentsPaginatedResponse {
  items: SourceDocumentRead[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export function listDocuments(bundleId: string, page?: number, pageSize?: number) {
  const params = new URLSearchParams({ bundle_id: bundleId });
  if (page !== undefined) params.set("page", String(page));
  if (pageSize !== undefined) params.set("page_size", String(pageSize));
  return request<DocumentsPaginatedResponse>(`/documents?${params.toString()}`);
}

export async function uploadDocument(
  bundleId: string,
  file: File,
  onProgress?: (progress: number) => void,
): Promise<SourceDocumentRead> {
  const formData = new FormData();
  formData.append("file", file);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/documents/upload?bundle_id=${encodeURIComponent(bundleId)}`);

    for (const [key, value] of Object.entries(getAuthHeaders())) {
      xhr.setRequestHeader(key, value);
    }

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      onProgress?.(Math.round((event.loaded / event.total) * 100));
    };

    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new Error(`Upload failed: ${xhr.status}`));
        return;
      }
      onProgress?.(100);
      try {
        resolve(JSON.parse(xhr.responseText) as SourceDocumentRead);
      } catch {
        reject(new Error("Upload failed: invalid response"));
      }
    };

    xhr.onerror = () => reject(new Error("Upload failed: network error"));
    xhr.onabort = () => reject(new Error("Upload cancelled"));
    xhr.send(formData);
  });
}

export function getDocumentDownloadUrl(documentId: string) {
  return `${API_BASE}/documents/${documentId}/download`;
}

// Assistant Attachments
export interface AssistantAttachmentUploadResponse {
  id: string;
  name: string;
  kind: "file" | "image";
  mime_type: string;
  size: number;
  extraction_status: "extracted" | "empty" | "unsupported" | "failed";
  extracted_text: string;
  error?: string | null;
}

export async function uploadAssistantAttachment(
  file: File,
  kind: "file" | "image",
): Promise<AssistantAttachmentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await fetch(`${API_BASE}/assistant/attachments?kind=${encodeURIComponent(kind)}`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: formData,
  });
  if (!resp.ok) throw new Error(`Assistant attachment upload failed: ${resp.status}`);
  return resp.json();
}

// Drafting
export interface DraftResponse {
  run_id: string;
  status: string;
}

export function draftSection(data: { project_id: string; section_key: string }) {
  return request<DraftResponse>("/drafting/sections", { method: "POST", body: JSON.stringify(data) });
}

export function redraftSection(data: { project_id: string; section_key: string; review_feedback?: string }) {
  return request<DraftResponse>("/drafting/sections/redraft", { method: "POST", body: JSON.stringify(data) });
}

// Execution Run
export interface ExecutionRunRead {
  id: string;
  project_id: string;
  run_type: string;
  status: string;
  input_json: Record<string, unknown> | null;
  output_json: Record<string, unknown> | null;
}

export function listExecutionRuns(projectId: string) {
  return request<ExecutionRunRead[]>(`/execution/runs?project_id=${projectId}`);
}

// Ops
export interface RuntimeSummary {
  queue_depth: number;
  failed_runs: number;
  draft_success_rate: number;
}

export function getRuntimeSummary() {
  return request<RuntimeSummary>("/ops/runtime-summary");
}

// Requirements
export interface RequirementItemRead {
  id: string;
  project_id: string;
  section_key: string;
  requirement_text: string;
  priority: string;
  status: string;
}

export function listRequirements(projectId: string) {
  return request<RequirementItemRead[]>(`/requirements?project_id=${projectId}`);
}

export function createRequirement(data: { project_id: string; section_key: string; requirement_text: string; priority?: string }) {
  return request<RequirementItemRead>("/requirements", { method: "POST", body: JSON.stringify(data) });
}

export function updateRequirement(id: string, data: { requirement_text?: string; priority?: string; section_key?: string; status?: string }) {
  return request<RequirementItemRead>(`/requirements/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

// Evidence
export interface EvidenceRead {
  id: string;
  project_id: string;
  source_document_id: string;
  quote_text: string;
  confidence: number | null;
}

export function listEvidence(projectId: string) {
  return request<EvidenceRead[]>(`/evidence?project_id=${projectId}`);
}

// Review Threads
export interface ReviewThreadRead {
  id: string;
  deliverable_section_id: string;
  status: string;
  opened_by: string;
  resolved_by: string | null;
}

export function listReviewThreads(sectionId: string) {
  return request<ReviewThreadRead[]>(`/review/threads?section_id=${sectionId}`);
}

// Review Comments
export interface ReviewCommentRead {
  id: string;
  review_thread_id: string;
  author_type: string;
  author_id: string;
  body: string;
  created_at: string;
}

export interface ReviewCommentCreate {
  thread_id: string;
  body: string;
  author_type?: string;
  author_id?: string;
}

export function listReviewComments(threadId: string) {
  return request<ReviewCommentRead[]>(`/review/threads/${threadId}/comments`);
}

export function createReviewComment(payload: ReviewCommentCreate) {
  return request<ReviewCommentRead>("/review/comments", { method: "POST", body: JSON.stringify(payload) });
}

// Review Decisions
export interface ReviewDecisionRead {
  id: string;
  section_id: string;
  decision: string;
  comment: string | null;
}

export interface ReviewDecisionCreate {
  section_id: string;
  decision: string;
  comment?: string | null;
}

export function submitReviewDecision(payload: ReviewDecisionCreate) {
  return request<ReviewDecisionRead>("/review/decisions", { method: "POST", body: JSON.stringify(payload) });
}

// Audit Events
export interface AuditEventRead {
  id: string;
  project_id: string;
  event_type: string;
  actor_type: string;
  actor_id: string;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export function listAuditEvents(projectId: string) {
  return request<AuditEventRead[]>(`/audit/events?project_id=${projectId}`);
}

// Export
export async function exportDeliverableDocx(deliverableId: string) {
  const blob = await requestBlob(`/export/deliverables/${deliverableId}/docx`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `deliverable-${deliverableId}.docx`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function exportDeliverablePdf(deliverableId: string) {
  const blob = await requestBlob(`/export/deliverables/${deliverableId}/pdf`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `deliverable-${deliverableId}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Auth
export interface CurrentUser {
  id: string;
  email: string;
  display_name: string;
  role: string;
  plan?: string;
  disabled?: boolean;
  email_verified?: boolean;
  org_id?: string;
  org_slug?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string | null;
}

export interface UserRegister {
  email: string;
  display_name: string;
  password: string;
  invitation_token?: string | null;
  org_name?: string | null;
  org_slug?: string | null;
  turnstile_token?: string | null;
}

export interface UserLogin {
  email: string;
  password: string;
  turnstile_token?: string | null;
}

export function registerUser(payload: UserRegister) {
  return request<CurrentUser>("/auth/register", { method: "POST", body: JSON.stringify(payload) });
}

export function loginUser(payload: UserLogin) {
  return request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload) });
}

export function getCurrentUser(token: string) {
  return request<CurrentUser>("/auth/me", { headers: { Authorization: `Bearer ${token}` } });
}

export interface UserUpdate {
  display_name?: string;
  current_password?: string;
  new_password?: string;
}

export function updateCurrentUser(payload: UserUpdate) {
  return request<CurrentUser>("/auth/me", { method: "PATCH", body: JSON.stringify(payload) });
}

// Password reset
export function requestPasswordReset(email: string, turnstileToken?: string | null) {
  return request<{ message: string }>(
    "/auth/password-reset",
    { method: "POST", body: JSON.stringify({ email, turnstile_token: turnstileToken || null }) },
  );
}

export function confirmPasswordReset(token: string, new_password: string) {
  return request<{ message: string }>("/auth/password-reset/confirm", { method: "POST", body: JSON.stringify({ token, new_password }) });
}

// Admin user management
export interface UsersPaginatedResponse {
  items: CurrentUser[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export function listUsers(page?: number, pageSize?: number) {
  const params = new URLSearchParams();
  if (page !== undefined) params.set("page", String(page));
  if (pageSize !== undefined) params.set("page_size", String(pageSize));
  const qs = params.toString();
  return request<UsersPaginatedResponse>(`/auth/users${qs ? `?${qs}` : ""}`);
}

export function updateUserRole(userId: string, role: string) {
  return request<CurrentUser>(`/auth/users/${userId}/role?role=${role}`, { method: "PATCH" });
}

export function setUserStatus(userId: string, disabled: boolean) {
  return request<CurrentUser>(`/auth/users/${userId}/status?disabled=${disabled}`, { method: "PATCH" });
}

// Email verification
export function verifyEmail(token: string) {
  return request<{ message: string }>(`/auth/verify-email?token=${token}`, { method: "POST" });
}

export function resendVerification(token: string, email?: string, turnstileToken?: string | null) {
  const params = new URLSearchParams();
  if (email) params.set("email", email);
  if (turnstileToken) params.set("turnstile_token", turnstileToken);
  const query = params.toString();
  return request<{ message: string }>(
    `/auth/resend-verification${query ? `?${query}` : ""}`,
    { method: "POST", headers: { Authorization: `Bearer ${token}` } },
  );
}

export function adminVerifyUser(userId: string) {
  return request<CurrentUser>(`/auth/users/${userId}/verify`, { method: "POST" });
}

// Account
export function deleteAccount(token: string) {
  return request<{ message: string }>("/auth/me", { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
}

export function exportAccountData(token: string) {
  return request<{ data: Record<string, unknown[]> }>("/auth/me/export", { headers: { Authorization: `Bearer ${token}` } });
}

// Subscription
export interface SubscriptionRead {
  plan: string;
  status: string;
  stripe_customer_id: string | null;
}

export function getSubscription(token: string) {
  return request<SubscriptionRead>("/auth/subscription", { headers: { Authorization: `Bearer ${token}` } });
}

export interface UsageQuotaRead {
  plan: string;
  monthly_workflow_limit: number;
  monthly_workflow_used: number;
  monthly_workflow_remaining: number | null;
  monthly_assistant_limit: number;
  monthly_assistant_used: number;
  monthly_assistant_remaining: number | null;
  monthly_indexing_limit: number;
  monthly_indexing_used: number;
  monthly_indexing_remaining: number | null;
  trial_window_start: string;
}

export function getUsageQuota() {
  return request<{ data: UsageQuotaRead }>("/usage/quota");
}

export interface BillingSummaryRead {
  plan: string;
  status: string;
  stripe_customer_id: string | null;
  monthly_workflow_limit: number;
  monthly_workflow_used: number;
  monthly_workflow_remaining: number | null;
  monthly_assistant_limit: number;
  monthly_assistant_used: number;
  monthly_assistant_remaining: number | null;
  monthly_indexing_limit: number;
  monthly_indexing_used: number;
  monthly_indexing_remaining: number | null;
  trial_window_start: string;
}

export function getBillingSummary() {
  return request<{ data: BillingSummaryRead }>("/auth/billing-summary");
}

// Billing
export interface CheckoutResult {
  url: string;
  session_id: string;
}

export function createCheckout(plan: string) {
  return request<CheckoutResult>(`/billing/checkout?plan=${plan}`, { method: "POST" });
}

export function updateSubscription(payload: { user_id: string; plan: string }) {
  return request<SubscriptionRead>("/auth/subscription", { method: "PATCH", body: JSON.stringify(payload) });
}

// Section Versions
export interface SectionVersionRead {
  id: string;
  deliverable_section_id: string;
  version_number: number;
  content_markdown: string | null;
  created_by_actor: string;
  generation_run_id: string | null;
}

export function listSectionVersions(sectionId: string) {
  return request<SectionVersionRead[]>(`/versions?section_id=${sectionId}`);
}

// Execution Run Retry
export function retryExecutionRun(runId: string) {
  return request<ExecutionRunRead>(`/execution/runs/${runId}/retry`, { method: "POST" });
}

// Bundle Reingest
export function reingestBundle(bundleId: string) {
  return request<BundleRead>(`/bundles/${bundleId}/reingest`, { method: "POST" });
}

// Health Detailed
export interface HealthDetailed {
  status: "ok" | "degraded";
  checks: {
    postgres: { status: string; detail?: string };
    redis: { status: string; detail?: string };
    minio: { status: string; detail?: string };
  };
}

export function getHealthDetailed() {
  return request<HealthDetailed>("/ops/health-detailed");
}

// Scenarios
export interface ScenarioRead {
  key: string;
  label: string;
  description: string;
}

export interface ScenarioDetail extends ScenarioRead {
  default_sections: string;
  requirement_keywords: string;
  drafting_system_prompt: string;
}

export interface ScenarioSection {
  section_key: string;
  title: string;
}

export function listScenarios() {
  return request<ScenarioRead[]>("/scenarios");
}

export function getScenarioDetail(key: string) {
  return request<ScenarioDetail>(`/scenarios/${key}`);
}

export function getScenarioSections(key: string) {
  return request<ScenarioSection[]>(`/scenarios/${key}/sections`);
}

// Retrieval Search
export interface SearchRequest {
  project_id: string;
  query: string;
  top_k?: number;
}

export interface SearchResult {
  chunk_id: string;
  source_document_id: string;
  content: string;
  score: number;
}

export function searchKnowledge(payload: SearchRequest) {
  return request<SearchResult[]>("/retrieval/search", { method: "POST", body: JSON.stringify(payload) });
}

// Parsed Assets
export interface ParsedAssetRead {
  id: string;
  source_document_id: string;
  parser_name: string;
  parser_version: string;
  content_json: Record<string, unknown> | null;
  layout_json: Record<string, unknown> | null;
}

export function listParsedAssets(sourceDocumentId: string) {
  return request<ParsedAssetRead[]>(`/parsed-assets?source_document_id=${sourceDocumentId}`);
}

// Knowledge Chunks (via evidence listing, chunks are embedded in evidence)
export interface KnowledgeChunkRead {
  id: string;
  project_id: string;
  source_document_id: string;
  chunk_index: number;
  content: string;
  metadata_json: Record<string, unknown> | null;
}

export function listKnowledgeChunks(projectId: string) {
  return request<KnowledgeChunkRead[]>(`/evidence/chunks?project_id=${projectId}`);
}

// Teams
export interface TeamMemberRead {
  id: string;
  user_id: string;
  user_email: string;
  user_display_name: string;
  role: string;
}

export interface TeamRead {
  id: string;
  org_id: string;
  name: string;
  slug: string;
  members?: TeamMemberRead[];
}

export interface TeamListResponse {
  items: TeamRead[];
  total: number;
}

export function createTeam(data: { name: string; slug: string }) {
  return request<TeamRead>("/teams", { method: "POST", body: JSON.stringify(data) });
}

export function listTeams() {
  return request<TeamListResponse>("/teams");
}

export function getTeam(id: string) {
  return request<TeamRead>(`/teams/${id}`);
}

export function updateTeam(id: string, data: { name?: string }) {
  return request<TeamRead>(`/teams/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export function deleteTeam(id: string) {
  return request<void>(`/teams/${id}`, { method: "DELETE" });
}

export function addTeamMember(teamId: string, data: { user_id: string; role?: string }) {
  return request<TeamMemberRead>(`/teams/${teamId}/members`, { method: "POST", body: JSON.stringify(data) });
}

export function removeTeamMember(teamId: string, userId: string) {
  return request<void>(`/teams/${teamId}/members/${userId}`, { method: "DELETE" });
}

// Organizations
export interface OrganizationRead {
  id: string;
  slug: string;
  name: string;
}

export function createOrganization(data: { name: string; slug: string }) {
  return request<OrganizationRead>("/organizations", { method: "POST", body: JSON.stringify(data) });
}

export function listOrganizations() {
  return request<OrganizationRead[]>("/organizations");
}

export function switchOrganization(orgId: string) {
  return request<CurrentUser>("/organizations/switch", { method: "POST", body: JSON.stringify({ org_id: orgId }) });
}

// Provider Configuration
export interface ProviderConfig {
  id: string;
  user_id: string;
  provider_type: "openai" | "anthropic";
  api_key: string;
  api_url: string | null;
  model: string;
  label: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProviderConfigCreate {
  provider_type: "openai" | "anthropic";
  api_key: string;
  api_url?: string;
  model: string;
  label: string;
  is_active?: boolean;
}

export interface TestConnectionResult {
  success: boolean;
  message: string;
  model: string | null;
}

export interface ProviderModelInfo {
  id: string;
  name?: string | null;
  owned_by?: string | null;
}

export interface ProviderModelsResult {
  models: ProviderModelInfo[];
}

// Chat
export interface ChatMessageRead {
  role: "user" | "assistant";
  content: string;
}

export interface ChatConversationRead {
  id: string;
  project_id: string | null;
  title: string | null;
  created_at: string | null;
}

export interface ChatHistoryRead {
  items: ChatMessageRead[];
  total: number;
}

export function listChatConversations(projectId?: string) {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request<ChatConversationRead[]>(`/chat/conversations${query}`);
}

export function getChatConversationMessages(conversationId: string) {
  return request<ChatHistoryRead>(`/chat/conversations/${conversationId}/messages`);
}

export function renameChatConversation(conversationId: string, title: string) {
  return request<ChatConversationRead>(`/chat/conversations/${conversationId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export function deleteChatConversation(conversationId: string) {
  return request<void>(`/chat/conversations/${conversationId}`, {
    method: "DELETE",
  });
}

export function listProviderConfigs() {
  return request<{ data: ProviderConfig[] }>("/auth/me/providers");
}

export function createProviderConfig(payload: ProviderConfigCreate) {
  return request<{ data: ProviderConfig }>("/auth/me/providers", { method: "POST", body: JSON.stringify(payload) });
}

export function updateProviderConfig(id: string, payload: Partial<ProviderConfigCreate>) {
  return request<{ data: ProviderConfig }>(`/auth/me/providers/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export function deleteProviderConfig(id: string) {
  return request<{ data: { deleted: boolean } }>(`/auth/me/providers/${id}`, { method: "DELETE" });
}

export type TestProviderConnectionPayload =
  | { config_id: string }
  | { provider_type: string; api_key: string; api_url?: string; model: string };

export function testProviderConnection(payload: TestProviderConnectionPayload) {
  if ("config_id" in payload) {
    return request<{ data: TestConnectionResult }>(
      `/auth/me/providers/test?config_id=${encodeURIComponent(payload.config_id)}`,
      { method: "POST" },
    );
  }
  return request<{ data: TestConnectionResult }>("/auth/me/providers/test", { method: "POST", body: JSON.stringify(payload) });
}

export type ListProviderModelsPayload =
  | { config_id: string }
  | { provider_type: "openai" | "anthropic"; api_key: string; api_url?: string };

export function listProviderModels(payload: ListProviderModelsPayload) {
  return request<{ data: ProviderModelsResult }>("/auth/me/providers/models", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Invitations
export interface InvitationRead {
  id: string;
  org_id: string;
  email: string;
  status: string;
  created_at?: string;
}

export function createInvitation(data: { email: string }) {
  return request<InvitationRead>("/invitations", { method: "POST", body: JSON.stringify(data) });
}

export function listInvitations() {
  return request<InvitationRead[]>("/invitations");
}

export function revokeInvitation(id: string) {
  return request<void>(`/invitations/${id}`, { method: "DELETE" });
}
