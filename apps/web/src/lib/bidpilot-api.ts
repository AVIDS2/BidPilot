const API_BASE = '/api/bidpilot';
const AUTH_BASE = '/api/auth';

function getAuthHeaders(): Record<string, string> {
  return {};
}

// Rate limit retry configuration
const RETRY_CONFIG = {
  maxRetries: 3,
  baseDelay: 1000,
  maxDelay: 10000
};

// Delay utility with exponential backoff
function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Check if error is rate limit (429)
function isRateLimitError(error: unknown): error is { status: number } {
  return (
    typeof error === 'object' &&
    error !== null &&
    'status' in error &&
    (error as { status: number }).status === 429
  );
}

export interface ApiRequestError extends Error {
  status: number;
  body?: unknown;
}

function createApiError(status: number, bodyText: string): ApiRequestError {
  const error = new Error(`API ${status}: ${bodyText}`) as ApiRequestError;
  error.status = status;
  if (bodyText) {
    try {
      error.body = JSON.parse(bodyText) as unknown;
    } catch {
      error.body = bodyText;
    }
  }
  return error;
}

export function getApiErrorDetail(error: unknown): unknown {
  if (typeof error !== 'object' || error === null || !('body' in error)) return undefined;
  const body = (error as { body?: unknown }).body;
  if (typeof body !== 'object' || body === null || !('detail' in body)) return undefined;
  return (body as { detail?: unknown }).detail;
}

async function request<T>(path: string, options?: RequestInit, base = API_BASE): Promise<T> {
  let lastError: unknown;

  for (let attempt = 0; attempt <= RETRY_CONFIG.maxRetries; attempt++) {
    try {
      const res = await fetch(`${base}${path}`, {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
          ...options?.headers
        },
        credentials: 'include',
        ...options
      });

      if (res.status === 429) {
        // Rate limit exceeded - extract retry-after or use exponential backoff
        const retryAfter = res.headers.get('Retry-After');
        const retryMs = retryAfter
          ? parseInt(retryAfter, 10) * 1000
          : Math.min(RETRY_CONFIG.baseDelay * Math.pow(2, attempt), RETRY_CONFIG.maxDelay);

        if (attempt < RETRY_CONFIG.maxRetries) {
          await delay(retryMs);
          continue; // Retry
        }
      }

      if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw createApiError(res.status, body);
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
          RETRY_CONFIG.maxDelay
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

async function requestBlob(path: string, options?: RequestInit, base = API_BASE): Promise<Blob> {
  let lastError: unknown;

  for (let attempt = 0; attempt <= RETRY_CONFIG.maxRetries; attempt++) {
    try {
      const res = await fetch(`${base}${path}`, {
        headers: { ...getAuthHeaders(), ...options?.headers },
        credentials: 'include',
        ...options
      });
      if (res.status === 429 && attempt < RETRY_CONFIG.maxRetries) {
        const retryAfter = res.headers.get('Retry-After');
        const retryMs = retryAfter
          ? parseInt(retryAfter, 10) * 1000
          : Math.min(RETRY_CONFIG.baseDelay * Math.pow(2, attempt), RETRY_CONFIG.maxDelay);
        await delay(retryMs);
        continue;
      }
      if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw createApiError(res.status, body);
      }
      return res.blob();
    } catch (error) {
      lastError = error;
      if (isRateLimitError(error) && attempt < RETRY_CONFIG.maxRetries) {
        const retryMs = Math.min(
          RETRY_CONFIG.baseDelay * Math.pow(2, attempt),
          RETRY_CONFIG.maxDelay
        );
        await delay(retryMs);
        continue;
      }
      throw error;
    }
  }

  throw lastError;
}

async function requestBlobWithTimeout(path: string, timeoutMs: number): Promise<Blob> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await requestBlob(path, { signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

const ASSISTANT_DOWNLOAD_PATH =
  /^\/(?:export\/deliverables\/[0-9a-f-]{36}\/(?:docx|pdf)|readiness\/packs\/[0-9a-f-]{36}\/(?:xlsx|docx))$/i;

/** Download a server-issued assistant artifact without exposing the bearer token in a URL. */
export async function downloadAssistantArtifact(path: string, filename: string) {
  if (!ASSISTANT_DOWNLOAD_PATH.test(path)) {
    throw new Error('Unsupported assistant download path');
  }

  const blob = await requestBlob(path);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
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
  return request<ProjectRead[]>('/projects');
}

export function createProject(data: { name: string; scenario_package: string }) {
  return request<ProjectRead>('/projects', { method: 'POST', body: JSON.stringify(data) });
}

export function createDemoProject() {
  return request<ProjectRead>('/projects/demo', { method: 'POST' });
}

export function getProject(id: string) {
  return request<ProjectRead>(`/projects/${id}`);
}

export function updateProjectStatus(id: string, status: string) {
  return request<ProjectRead>(`/projects/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status })
  });
}

export function deleteProject(id: string) {
  return request<void>(`/projects/${id}`, { method: 'DELETE' });
}

// Notification preferences
export interface NotificationPreferencesRead {
  in_app_enabled: boolean;
  email_enabled: boolean;
  review_updates: boolean;
  agent_updates: boolean;
  radar_updates: boolean;
  material_updates: boolean;
}

export function getNotificationPreferences() {
  return request<NotificationPreferencesRead>('/notifications/preferences');
}

export function updateNotificationPreferences(payload: Partial<NotificationPreferencesRead>) {
  return request<NotificationPreferencesRead>('/notifications/preferences', {
    method: 'PATCH',
    body: JSON.stringify(payload)
  });
}

// Tender radar
export type NoticeSourceKind = 'rss' | 'json_feed' | 'webhook';
export type RadarNoticeType = 'intent' | 'tender' | 'prequalification' | 'rfi' | 'other';
export type RadarNoticeStatus = 'new' | 'saved' | 'ignored' | 'converted';
export type RadarOverviewView = 'recommended' | 'all' | 'intent' | 'tender' | 'saved' | 'ignored';

export interface NoticeSourceRead {
  id: string;
  name: string;
  kind: NoticeSourceKind;
  endpoint_url: string | null;
  is_active: boolean;
  polling_interval_minutes: number;
  last_polled_at: string | null;
  last_success_at: string | null;
  last_error_code: string | null;
  notice_count: number;
}

export interface NoticeSubscriptionRead {
  id: string;
  name: string;
  keywords: string[];
  regions: string[];
  categories: string[];
  budget_min: number | null;
  budget_max: number | null;
  is_active: boolean;
  match_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface NoticeMatchRead {
  subscription_id: string;
  subscription_name: string;
  score: number;
  reasons: string[];
}

export interface RadarNoticeRead {
  id: string;
  source_id: string;
  source_name: string;
  external_id: string;
  title: string;
  buyer_name: string | null;
  notice_type: RadarNoticeType;
  region: string | null;
  category: string | null;
  budget_amount: number | null;
  published_at: string | null;
  deadline_at: string | null;
  source_url: string;
  summary: string | null;
  status: RadarNoticeStatus;
  converted_project_id: string | null;
  created_at: string | null;
  matches: NoticeMatchRead[];
}

export interface RadarTrendPoint {
  day: string;
  notice_count: number;
}

export interface RadarSummaryRead {
  active_source_count: number;
  source_attention_count: number;
  active_subscription_count: number;
  recommended_count: number;
  saved_count: number;
  due_soon_count: number;
  trends: RadarTrendPoint[];
}

export interface RadarOverviewRead {
  summary: RadarSummaryRead;
  sources: NoticeSourceRead[];
  subscriptions: NoticeSubscriptionRead[];
  notices: RadarNoticeRead[];
}

export function getRadarOverview(
  params: {
    view?: RadarOverviewView;
    query?: string;
    noticeType?: RadarNoticeType;
  } = {}
) {
  const query = new URLSearchParams();
  if (params.view) query.set('view', params.view);
  if (params.query?.trim()) query.set('query', params.query.trim());
  if (params.noticeType) query.set('notice_type', params.noticeType);
  const suffix = query.size ? `?${query.toString()}` : '';
  return request<RadarOverviewRead>(`/radar/overview${suffix}`);
}

export function createRadarSource(data: {
  name: string;
  kind: NoticeSourceKind;
  endpoint_url?: string;
  polling_interval_minutes?: number;
}) {
  return request<NoticeSourceRead>('/radar/sources', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export function updateRadarSource(
  sourceId: string,
  data: Partial<
    Pick<NoticeSourceRead, 'name' | 'endpoint_url' | 'is_active' | 'polling_interval_minutes'>
  >
) {
  return request<NoticeSourceRead>(`/radar/sources/${sourceId}`, {
    method: 'PATCH',
    body: JSON.stringify(data)
  });
}

export function pollRadarSource(sourceId: string) {
  return request<{
    source_id: string;
    status: 'succeeded' | 'failed' | 'skipped';
    discovered_count: number;
    created_count: number;
    updated_count: number;
    error_code: string | null;
  }>(`/radar/sources/${sourceId}/poll`, { method: 'POST' });
}

export function createRadarSubscription(data: {
  name: string;
  keywords?: string[];
  regions?: string[];
  categories?: string[];
  budget_min?: number;
  budget_max?: number;
}) {
  return request<NoticeSubscriptionRead>('/radar/subscriptions', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export function updateRadarNoticeStatus(noticeId: string, status: 'new' | 'saved' | 'ignored') {
  return request<RadarNoticeRead>(`/radar/notices/${noticeId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status })
  });
}

export function convertRadarNoticeToProject(noticeId: string, projectName?: string) {
  return request<{ notice: RadarNoticeRead; project_id: string; project_slug: string }>(
    `/radar/notices/${noticeId}/convert`,
    { method: 'POST', body: JSON.stringify({ project_name: projectName || undefined }) }
  );
}

export type ProjectRole = 'owner' | 'manager' | 'contributor' | 'reviewer' | 'viewer';

export interface ProjectMemberRead {
  user_id: string;
  display_name: string;
  role: ProjectRole;
  source: 'membership';
}

export function listProjectMembers(projectId: string) {
  return request<ProjectMemberRead[]>(`/projects/${projectId}/members`);
}

export function addProjectMember(projectId: string, data: { user_id: string; role: ProjectRole }) {
  return request<ProjectMemberRead>(`/projects/${projectId}/members`, {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export function updateProjectMember(
  projectId: string,
  userId: string,
  data: { role: ProjectRole }
) {
  return request<ProjectMemberRead>(`/projects/${projectId}/members/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(data)
  });
}

export function removeProjectMember(projectId: string, userId: string) {
  return request<void>(`/projects/${projectId}/members/${userId}`, { method: 'DELETE' });
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
  return request<BundleRead>('/bundles', { method: 'POST', body: JSON.stringify(data) });
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
  return request<DeliverableRead>('/deliverables', { method: 'POST', body: JSON.stringify(data) });
}

// Deliverable Sections
export interface DeliverableSectionRead {
  id: string;
  deliverable_id: string;
  section_key: string;
  title: string;
  status: string;
  approved_version_id?: string | null;
  assignee_type?: string;
  sort_order?: number;
}

export function listDeliverableSections(deliverableId: string) {
  return request<DeliverableSectionRead[]>(`/deliverables/${deliverableId}/sections`);
}

export function createDeliverableSection(data: {
  deliverable_id: string;
  section_key: string;
  title: string;
  sort_order?: number;
}) {
  return request<DeliverableSectionRead>('/deliverables/sections', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export function updateDeliverableSection(
  sectionId: string,
  data: { title?: string; section_key?: string; sort_order?: number }
) {
  return request<DeliverableSectionRead>(`/deliverables/sections/${sectionId}`, {
    method: 'PATCH',
    body: JSON.stringify(data)
  });
}

export function reorderDeliverableSections(deliverableId: string, sectionIds: string[]) {
  return request<DeliverableSectionRead[]>(`/deliverables/${deliverableId}/sections/reorder`, {
    method: 'PUT',
    body: JSON.stringify({ section_ids: sectionIds })
  });
}

export function deleteDeliverableSection(sectionId: string, force = false) {
  const qs = force ? '?force=true' : '';
  return request<{ deleted: boolean; section_id: string }>(
    `/deliverables/sections/${sectionId}${qs}`,
    {
      method: 'DELETE'
    }
  );
}

// Documents
export interface SourceDocumentRead {
  id: string;
  bundle_id: string;
  storage_key: string;
  source_url: string | null;
  mime_type: string;
  original_filename: string;
  parse_status: string;
  parse_attempt_count: number;
  parser_name: string | null;
  parser_version: string | null;
  parse_error_code: string | null;
  parse_error_detail: string | null;
  parse_retryable: boolean;
  index_status: string;
  index_error_code: string | null;
  version_number: number;
  supersedes_document_id: string | null;
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
  if (page !== undefined) params.set('page', String(page));
  if (pageSize !== undefined) params.set('page_size', String(pageSize));
  return request<DocumentsPaginatedResponse>(`/documents?${params.toString()}`);
}

export async function uploadDocument(
  bundleId: string,
  file: File,
  onProgress?: (progress: number) => void,
  assistantAttachmentId?: string,
  deferIngest = false
): Promise<SourceDocumentRead> {
  const formData = new FormData();
  formData.append('file', file);
  if (assistantAttachmentId) formData.append('assistant_attachment_id', assistantAttachmentId);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const params = new URLSearchParams({ bundle_id: bundleId });
    if (deferIngest) params.set('defer_ingest', 'true');
    xhr.open('POST', `${API_BASE}/documents/upload?${params.toString()}`);
    xhr.withCredentials = true;

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
        reject(new Error('Upload failed: invalid response'));
      }
    };

    xhr.onerror = () => reject(new Error('Upload failed: network error'));
    xhr.onabort = () => reject(new Error('Upload cancelled'));
    xhr.send(formData);
  });
}

export function getDocumentDownloadUrl(documentId: string) {
  return `${API_BASE}/documents/${documentId}/download`;
}

export function getDocumentBlob(documentId: string, timeoutMs = 20_000) {
  return requestBlobWithTimeout(`/documents/${documentId}/download`, timeoutMs);
}

// Assistant Attachments
export interface AssistantAttachmentUploadResponse {
  id: string;
  name: string;
  kind: 'file' | 'image';
  mime_type: string;
  size: number;
  extraction_status: 'extracted' | 'empty' | 'unsupported' | 'failed';
  extracted_text: string;
  error?: string | null;
}

export async function uploadAssistantAttachment(
  file: File,
  kind: 'file' | 'image'
): Promise<AssistantAttachmentUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const resp = await fetch(`${API_BASE}/assistant/attachments?kind=${encodeURIComponent(kind)}`, {
    method: 'POST',
    headers: getAuthHeaders(),
    credentials: 'include',
    body: formData
  });
  if (!resp.ok) {
    let detail = '';
    try {
      const body = (await resp.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      // Keep the HTTP status as the fallback when the server did not return JSON.
    }
    throw new Error(detail || `Assistant attachment upload failed: ${resp.status}`);
  }
  return resp.json();
}

// Drafting
export interface DraftResponse {
  run_id: string;
  status: string;
}

export function draftSection(data: {
  project_id: string;
  section_key: string;
  section_id?: string;
  provider_config_id?: string;
  reasoning_effort?: 'low' | 'medium' | 'high' | 'extra' | 'max';
  max_iterations?: number;
}) {
  return request<DraftResponse>('/drafting/sections', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export function redraftSection(data: {
  project_id: string;
  section_key: string;
  section_id?: string;
  review_feedback?: string;
  provider_config_id?: string;
  reasoning_effort?: 'low' | 'medium' | 'high' | 'extra' | 'max';
  max_iterations?: number;
}) {
  return request<DraftResponse>('/drafting/sections/redraft', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

// Execution Run
export interface ExecutionRunRead {
  id: string;
  project_id: string;
  run_type: string;
  status: string;
  parent_execution_run_id: string | null;
  attempt_number: number;
  runtime_run_id: string | null;
  input_json: Record<string, unknown> | null;
  output_json: Record<string, unknown> | null;
}

export function listExecutionRuns(projectId: string) {
  return request<ExecutionRunRead[]>(`/execution/runs?project_id=${projectId}`);
}

// Response plans
export interface ResponsePlanRead {
  id: string;
  project_id: string;
  deliverable_id: string;
  version_number: number;
  status: string;
  source_fingerprint: string;
  unmapped_requirement_ids: string[];
  created_by_actor: string;
  created_at: string | null;
}

export interface ResponsePlanRequirementRead {
  id: string;
  requirement_id: string;
  requirement_lock_version: number;
  requirement_text: string;
  priority: string;
  owner_user_id: string | null;
  verification_status: string;
  assignment_reason: string;
}

export interface ResponsePlanEvidenceBindingRead {
  id: string;
  evidence_set_id: string;
  execution_run_id: string;
  generation_iteration: number;
  evidence_set_status: string;
  unmet_requirement_ids: string[];
  degraded_reasons: string[];
  content_plan: Record<string, unknown>;
  created_at: string | null;
}

export interface ResponsePlanSectionRead {
  id: string;
  deliverable_section_id: string;
  section_key: string;
  title: string;
  sort_order: number;
  status: string;
  requirements: ResponsePlanRequirementRead[];
  evidence_bindings: ResponsePlanEvidenceBindingRead[];
}

export interface ResponsePlanDetailRead extends ResponsePlanRead {
  sections: ResponsePlanSectionRead[];
}

export function listResponsePlans(projectId: string) {
  return request<ResponsePlanRead[]>(`/response-plans?project_id=${encodeURIComponent(projectId)}`);
}

export function getResponsePlan(projectId: string, responsePlanId: string) {
  const query = new URLSearchParams({ project_id: projectId });
  return request<ResponsePlanDetailRead>(`/response-plans/${responsePlanId}?${query.toString()}`);
}

// Ops
export interface RuntimeSummary {
  queue_depth: number;
  failed_runs: number;
  draft_success_rate: number;
}

export function getRuntimeSummary() {
  return request<RuntimeSummary>('/ops/runtime-summary');
}

export interface RuntimeEventRead {
  event_id: string;
  run_id: string;
  parent_event_id: string | null;
  sequence: number;
  type: string;
  public_summary: string;
  payload: Record<string, unknown>;
  schema_version: string;
  timestamp: string;
}

export interface RuntimeEventsResponse {
  items: RuntimeEventRead[];
}

export interface RuntimeLinkedWorkflowRun {
  id: string;
  status: string;
  project_id: string | null;
  execution_run_id: string | null;
  engine: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface RuntimeRunRead {
  id: string;
  kind: string;
  status: string;
  project_id: string | null;
  conversation_id: string | null;
  execution_run_id: string | null;
  engine: string;
  trace_id: string;
  parent_run_id: string | null;
  linked_workflow_runs?: RuntimeLinkedWorkflowRun[];
}

export interface RuntimeRunListItem {
  id: string;
  kind: string;
  status: string;
  project_id: string | null;
  project_name: string | null;
  engine: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  latest_event_summary: string | null;
}

export interface RuntimeChildRunRead {
  id: string;
  parent_run_id: string;
  kind: string;
  status: string;
  profile: string | null;
  mode: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  latest_event_summary: string | null;
}

export function listRuntimeRuns(
  limit = 50,
  conversationId?: string | null,
  kinds?: readonly string[]
) {
  const params = new URLSearchParams({
    limit: String(Math.min(Math.max(limit, 1), 100))
  });
  if (conversationId) params.set('conversation_id', conversationId);
  for (const kind of kinds ?? []) {
    if (kind) params.append('kind', kind);
  }
  return request<RuntimeRunListItem[]>(`/runtime/runs?${params.toString()}`);
}

export function listRuntimeEvents(runId: string, afterSequence = 0) {
  return request<RuntimeEventsResponse>(
    `/runtime/runs/${encodeURIComponent(runId)}/events?after_sequence=${afterSequence}`
  );
}

export function listRuntimeChildRuns(runId: string, limit = 20) {
  const params = new URLSearchParams({
    limit: String(Math.min(Math.max(limit, 1), 100))
  });
  return request<RuntimeChildRunRead[]>(
    `/runtime/runs/${encodeURIComponent(runId)}/children?${params.toString()}`
  );
}

export function cancelRuntimeWorkflow(runId: string) {
  return request<RuntimeRunRead>(`/runtime/runs/${encodeURIComponent(runId)}/cancel`, {
    method: 'POST'
  });
}

// Requirements
export interface BidRequirementProfileRead {
  id: string;
  requirement_id: string;
  bid_category: string;
  is_mandatory: boolean;
  score_weight: number | null;
  risk_level: string;
  coverage_status: string;
  evidence_status: string;
  deadline_at: string | null;
  submission_metadata_json: Record<string, unknown> | null;
  updated_at: string;
}

export interface RequirementItemRead {
  id: string;
  project_id: string;
  section_key: string;
  requirement_text: string;
  original_text: string | null;
  source_document_id: string | null;
  source_document_name: string | null;
  source_locator_json: Record<string, unknown> | null;
  priority: string;
  status: string;
  owner_user_id: string | null;
  reviewer_user_id: string | null;
  due_at: string | null;
  verification_status: string;
  extraction_confidence: number | null;
  lock_version: number;
  updated_at: string;
  bid_profile: BidRequirementProfileRead | null;
}

export interface RequirementEvidenceLinkRead {
  id: string;
  requirement_id: string;
  evidence_id: string;
  relation_type: string;
  verification_status: string;
  quote_text: string;
  source_document_id: string | null;
  source_document_name: string | null;
  locator_json: Record<string, unknown> | null;
  confidence: number | null;
  created_at: string;
}

export interface RequirementClaimRead {
  id: string;
  project_id: string;
  requirement_id: string;
  claim_text: string;
  claim_type: string;
  status: string;
  coverage_role: string;
  section_version_id: string | null;
  generation_run_id: string | null;
  created_by_actor: string;
  created_by_user_id: string | null;
  evidence_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface RequirementDecisionRead {
  id: string;
  requirement_id: string;
  decision_type: string;
  rationale: string;
  status: string;
  requested_by_user_id: string;
  approved_by_user_id: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface RequirementDetailRead extends RequirementItemRead {
  evidence_links: RequirementEvidenceLinkRead[];
  claims: RequirementClaimRead[];
  decisions: RequirementDecisionRead[];
}

export interface RequirementFilters {
  bid_category?: string;
  coverage_status?: string;
  evidence_status?: string;
  risk_level?: string;
  owner_user_id?: string;
  verification_status?: string;
}

export interface RequirementCreateInput {
  project_id: string;
  section_key: string;
  requirement_text: string;
  original_text?: string | null;
  source_document_id?: string | null;
  source_locator_json?: Record<string, unknown> | null;
  priority?: string;
  owner_user_id?: string | null;
  reviewer_user_id?: string | null;
  due_at?: string | null;
  extraction_confidence?: number | null;
  bid_profile?: {
    bid_category?: string;
    is_mandatory?: boolean;
    score_weight?: number | null;
    risk_level?: string;
    deadline_at?: string | null;
    submission_metadata_json?: Record<string, unknown> | null;
  } | null;
}

export interface RequirementUpdateInput {
  lock_version?: number;
  requirement_text?: string;
  original_text?: string | null;
  source_document_id?: string | null;
  source_locator_json?: Record<string, unknown> | null;
  priority?: string;
  section_key?: string;
  status?: string;
  owner_user_id?: string | null;
  reviewer_user_id?: string | null;
  due_at?: string | null;
  verification_status?: string;
  extraction_confidence?: number | null;
  bid_profile?: {
    bid_category?: string;
    is_mandatory?: boolean;
    score_weight?: number | null;
    risk_level?: string;
    deadline_at?: string | null;
    submission_metadata_json?: Record<string, unknown> | null;
  } | null;
}

export function listRequirements(projectId: string, filters: RequirementFilters = {}) {
  const params = new URLSearchParams({ project_id: projectId });
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  return request<RequirementItemRead[]>(`/requirements?${params.toString()}`);
}

export function getRequirement(id: string) {
  return request<RequirementDetailRead>(`/requirements/${id}`);
}

export function createRequirement(data: RequirementCreateInput) {
  return request<RequirementItemRead>('/requirements', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export function updateRequirement(id: string, data: RequirementUpdateInput) {
  return request<RequirementItemRead>(`/requirements/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data)
  });
}

export function bulkAssignRequirements(data: {
  requirement_ids: string[];
  lock_versions: Record<string, number>;
  owner_user_id?: string | null;
  reviewer_user_id?: string | null;
}) {
  return request<RequirementItemRead[]>('/requirements/bulk-assign', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export function verifyRequirementEvidenceLink(requirementId: string, linkId: string) {
  return request<RequirementEvidenceLinkRead>(`/requirements/${requirementId}/evidence/${linkId}`, {
    method: 'PATCH',
    body: JSON.stringify({ verification_status: 'verified' })
  });
}

export function verifyRequirementClaim(requirementId: string, claimId: string) {
  return request<RequirementClaimRead>(`/requirements/${requirementId}/claims/${claimId}/verify`, {
    method: 'POST'
  });
}

export interface ReadinessRequirementRead {
  id: string;
  section_key: string;
  requirement_text: string;
  bid_category: string;
  is_mandatory: boolean;
  score_weight: number | null;
  risk_level: string;
  coverage_status: string;
  evidence_status: string;
  verification_status: string;
  owner_user_id: string | null;
  reviewer_user_id: string | null;
  due_at: string | null;
  source_locator_json: Record<string, unknown> | null;
}

export interface BidReadinessSummary {
  formula_version: string;
  project_id: string;
  project_name: string;
  generated_at: string;
  source_fingerprint: string;
  score_label: string;
  readiness_score: number;
  counts: {
    total: number;
    mandatory: number;
    scored: number;
    covered: number;
    partial: number;
    uncovered: number;
    disputed: number;
    not_applicable: number;
    accepted_risk: number;
    verified: number;
    assigned: number;
  };
  scores: {
    mandatory_closure: number;
    scored_coverage: number;
    verification: number;
    assignment: number;
  };
  requirements: ReadinessRequirementRead[];
  mandatory_gaps: ReadinessRequirementRead[];
  evidence_gaps: ReadinessRequirementRead[];
  contradictions: ReadinessRequirementRead[];
  overdue: ReadinessRequirementRead[];
  qualifications: ReadinessRequirementRead[];
  workload: { unassigned: number; by_owner: Record<string, number> };
}

export interface ReadinessPackRead {
  id: string;
  project_id: string;
  version_number: number;
  formula_version: string;
  source_fingerprint: string;
  status: string;
  summary_json: Record<string, unknown>;
  xlsx_storage_key: string | null;
  docx_storage_key: string | null;
  generated_by_user_id: string | null;
  created_at: string;
}

export function getReadinessSummary(projectId: string) {
  return request<BidReadinessSummary>(`/readiness/projects/${projectId}`);
}

export function generateReadinessPack(projectId: string) {
  return request<ReadinessPackRead>(`/readiness/projects/${projectId}/packs`, { method: 'POST' });
}

export async function downloadReadinessPack(packId: string, format: 'xlsx' | 'docx') {
  const blob = await requestBlob(`/readiness/packs/${packId}/${format}`);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `bid-readiness-${packId}.${format}`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
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
  return request<ReviewCommentRead>('/review/comments', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

// Review Decisions
export interface ReviewDecisionRead {
  id: string;
  section_id: string;
  section_version_id: string;
  decision: string;
  comment: string | null;
}

export interface CollaborationBoardRead {
  project_id: string;
  members: Array<{ user_id: string; display_name: string; role: string }>;
  requirement_items: Array<{
    requirement_id: string;
    section_key: string;
    requirement_text: string;
    status: string;
    priority: string;
    verification_status: string;
    owner_user_id: string | null;
    owner_display_name: string | null;
    reviewer_user_id: string | null;
    reviewer_display_name: string | null;
    due_at: string | null;
    overdue: boolean;
    needs_assignment: boolean;
    risk_level: string | null;
    coverage_status: string | null;
  }>;
  unassigned_requirement_count: number;
  overdue_requirement_count: number;
  review_required_count: number;
  open_review_thread_count: number;
  active_workflow_count: number;
}

export function getCollaborationBoard(projectId: string) {
  return request<CollaborationBoardRead>(
    `/collaboration/projects/${encodeURIComponent(projectId)}/board`
  );
}

export interface ReviewDecisionCreate {
  section_id: string;
  section_version_id: string;
  decision: string;
  comment?: string | null;
}

export function submitReviewDecision(payload: ReviewDecisionCreate) {
  return request<ReviewDecisionRead>('/review/decisions', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
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
  const a = document.createElement('a');
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
  const a = document.createElement('a');
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
  verification_email_accepted?: boolean | null;
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
  return request<CurrentUser>(
    '/register',
    { method: 'POST', body: JSON.stringify(payload) },
    AUTH_BASE
  );
}

export function loginUser(payload: UserLogin) {
  return request<TokenResponse>(
    '/login',
    { method: 'POST', body: JSON.stringify(payload) },
    AUTH_BASE
  );
}

export function getCurrentUser(_token?: string) {
  return request<CurrentUser>('/me', undefined, AUTH_BASE);
}

export interface UserUpdate {
  display_name?: string;
  current_password?: string;
  new_password?: string;
}

export function updateCurrentUser(payload: UserUpdate) {
  return request<CurrentUser>('/auth/me', { method: 'PATCH', body: JSON.stringify(payload) });
}

// Password reset
export function requestPasswordReset(email: string, turnstileToken?: string | null) {
  return request<{ message: string }>('/auth/password-reset', {
    method: 'POST',
    body: JSON.stringify({ email, turnstile_token: turnstileToken || null })
  });
}

export function confirmPasswordReset(token: string, new_password: string) {
  return request<{ message: string }>('/auth/password-reset/confirm', {
    method: 'POST',
    body: JSON.stringify({ token, new_password })
  });
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
  if (page !== undefined) params.set('page', String(page));
  if (pageSize !== undefined) params.set('page_size', String(pageSize));
  const qs = params.toString();
  return request<UsersPaginatedResponse>(`/auth/users${qs ? `?${qs}` : ''}`);
}

export function updateUserRole(userId: string, role: string) {
  return request<CurrentUser>(`/auth/users/${userId}/role?role=${role}`, { method: 'PATCH' });
}

export function setUserStatus(userId: string, disabled: boolean) {
  return request<CurrentUser>(`/auth/users/${userId}/status?disabled=${disabled}`, {
    method: 'PATCH'
  });
}

// Email verification
export function verifyEmail(token: string) {
  return request<TokenResponse>(`/auth/verify-email?token=${token}`, { method: 'POST' });
}

export function resendVerification(
  _token?: string | null,
  email?: string,
  turnstileToken?: string | null
) {
  const params = new URLSearchParams();
  if (email) params.set('email', email);
  if (turnstileToken) params.set('turnstile_token', turnstileToken);
  const query = params.toString();
  return request<{ message: string }>(`/auth/resend-verification${query ? `?${query}` : ''}`, {
    method: 'POST'
  });
}

export function adminVerifyUser(userId: string) {
  return request<CurrentUser>(`/auth/users/${userId}/verify`, { method: 'POST' });
}

// Account
export function deleteAccount(_token: string) {
  return request<{ message: string }>('/auth/me', { method: 'DELETE' });
}

export function exportAccountData(_token: string) {
  return request<{ data: Record<string, unknown[]> }>('/auth/me/export');
}

// Subscription
export interface SubscriptionRead {
  plan: string;
  status: string;
  stripe_customer_id: string | null;
}

export function getSubscription(_token: string) {
  return request<SubscriptionRead>('/auth/subscription');
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
  official_model_usage: ModelUsageSourceRead;
  byok_model_usage: ModelUsageSourceRead;
  trial_window_start: string;
}

export interface ModelUsageSourceRead {
  input_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  total_tokens: number;
  reserved_tokens: number;
  token_limit: number | null;
  remaining_tokens: number | null;
  cost_available: boolean;
}

export interface OrganizationUsageBudgetRead {
  official_monthly_token_limit: number | null;
  byok_monthly_token_limit: number | null;
  official_platform_monthly_token_ceiling: number | null;
  effective_official_monthly_token_limit: number | null;
  can_manage: boolean;
}

export function getUsageQuota() {
  return request<{ data: UsageQuotaRead }>('/usage/quota');
}

export function getOrganizationUsageBudget() {
  return request<OrganizationUsageBudgetRead>('/usage/budget');
}

export function updateOrganizationUsageBudget(
  payload: Partial<
    Pick<OrganizationUsageBudgetRead, 'official_monthly_token_limit' | 'byok_monthly_token_limit'>
  >
) {
  return request<OrganizationUsageBudgetRead>('/usage/budget', {
    method: 'PUT',
    body: JSON.stringify(payload)
  });
}

export interface BillingSummaryRead {
  plan: string;
  status: string;
  stripe_customer_id: string | null;
  entitlement_source: 'organization' | 'legacy' | 'starter';
  seat_limit: number;
  is_billing_owner: boolean;
  monthly_workflow_limit: number;
  monthly_workflow_used: number;
  monthly_workflow_remaining: number | null;
  monthly_assistant_limit: number;
  monthly_assistant_used: number;
  monthly_assistant_remaining: number | null;
  monthly_indexing_limit: number;
  monthly_indexing_used: number;
  monthly_indexing_remaining: number | null;
  official_model_usage: ModelUsageSourceRead;
  byok_model_usage: ModelUsageSourceRead;
  trial_window_start: string;
}

export function getBillingSummary() {
  return request<{ data: BillingSummaryRead }>('/auth/billing-summary');
}

// Billing
export interface CheckoutResult {
  url: string;
  session_id: string;
  mode?: 'checkout' | 'portal';
}

export function createCheckout(plan: string) {
  return request<CheckoutResult>(`/billing/checkout?plan=${plan}`, { method: 'POST' });
}

export function createBillingPortal() {
  return request<CheckoutResult>('/billing/portal', { method: 'POST' });
}

export function updateSubscription(payload: { user_id: string; plan: string }) {
  return request<SubscriptionRead>('/auth/subscription', {
    method: 'PATCH',
    body: JSON.stringify(payload)
  });
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
  return request<ExecutionRunRead>(`/execution/runs/${runId}/retry`, { method: 'POST' });
}

// Bundle Reingest
export function reingestBundle(bundleId: string) {
  return request<BundleRead>(`/bundles/${bundleId}/reingest`, { method: 'POST' });
}

export function reindexBundle(bundleId: string) {
  return request<BundleRead>(`/bundles/${bundleId}/reindex`, { method: 'POST' });
}

// Health Detailed
export interface HealthDetailed {
  status: 'ok' | 'degraded';
  checks: {
    postgres: { status: string; detail?: string };
    redis: { status: string; detail?: string };
    minio: { status: string; detail?: string };
  };
}

export function getHealthDetailed() {
  return request<HealthDetailed>('/ops/health-detailed');
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
  return request<ScenarioRead[]>('/scenarios');
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
  return request<SearchResult[]>('/retrieval/search', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
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

// Governed Project Memory / Bid Wiki
export type MemoryScope = 'user_private' | 'project_shared' | 'org_shared';
export type MemoryKind =
  | 'preference'
  | 'fact'
  | 'decision'
  | 'procedure'
  | 'risk'
  | 'summary'
  | 'entity_note';
export type MemoryStatus = 'proposed' | 'active' | 'superseded' | 'rejected' | 'deleted';

export interface MemoryCitationRead {
  source_type:
    | 'knowledge_chunk'
    | 'requirement_item'
    | 'evidence_item'
    | 'chat_message'
    | 'audit_event'
    | 'human_decision';
  source_id: string;
  label: string;
  locator_json: Record<string, unknown> | null;
}

export interface MemoryGraphEntityProposalRead {
  item_id: string;
  canonical_name: string;
  entity_type: string;
  evidence_labels: string[];
  review_status: 'pending' | 'accepted' | 'rejected';
  review_note: string | null;
}

export interface MemoryGraphRelationProposalRead {
  item_id: string;
  subject: string;
  predicate: string;
  object: string;
  evidence_labels: string[];
  review_status: 'pending' | 'accepted' | 'rejected';
  review_note: string | null;
}

export interface MemoryGraphProposalRead {
  schema_version: string;
  entities: MemoryGraphEntityProposalRead[];
  relations: MemoryGraphRelationProposalRead[];
}

export interface MemoryRead {
  id: string;
  org_id: string;
  project_id: string | null;
  owner_user_id: string | null;
  scope: MemoryScope;
  kind: MemoryKind;
  status: MemoryStatus;
  title: string;
  body_markdown: string;
  citations: MemoryCitationRead[];
  graph_proposal?: MemoryGraphProposalRead | null;
  expires_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface MemoryPortfolioProjectRead {
  project_id: string;
  project_name: string;
  active_shared_count: number;
  proposed_shared_count: number | null;
  latest_shared_memory_at: string | null;
  latest_compilation_status: string | null;
  latest_compilation_at: string | null;
}

export interface MemoryEvidenceMapNodeRead {
  id: string;
  node_type: 'memory' | 'source';
  label: string;
  memory_kind: string | null;
  source_type: string | null;
}

export interface MemoryEvidenceMapEdgeRead {
  id: string;
  source: string;
  target: string;
  predicate: 'cites';
}

export interface MemoryEvidenceMapRead {
  project_id: string;
  nodes: MemoryEvidenceMapNodeRead[];
  edges: MemoryEvidenceMapEdgeRead[];
  truncated: boolean;
}

export interface MemoryCompilationRead {
  id: string;
  project_id: string;
  bundle_id: string | null;
  status: string;
  input_source_count: number;
  result_json: Record<string, unknown> | null;
  error_code: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface MemoryGraphExtractionRead {
  run_id: string;
  runtime_run_id: string;
  project_id: string;
  memory_record_id: string;
  status: string;
  reused: boolean;
}

export interface MemoryGraphReviewDecisionRead {
  item_id: string;
  item_type: 'entity' | 'relation';
  decision: 'accepted' | 'rejected';
  decision_note: string | null;
  reviewed_at: string | null;
}

export function listProjectMemory(projectId: string, includeProposed = false) {
  const params = new URLSearchParams({
    project_id: projectId,
    scope: 'project_shared'
  });
  if (includeProposed) params.set('include_proposed', 'true');
  return request<MemoryRead[]>(`/memory?${params.toString()}`);
}

export function listKnowledgePortfolio(limit = 50) {
  return request<MemoryPortfolioProjectRead[]>(`/memory/portfolio?limit=${limit}`);
}

export function getMemoryEvidenceMap(projectId: string, maxRecords = 40, maxSources = 80) {
  const params = new URLSearchParams({
    project_id: projectId,
    max_records: String(maxRecords),
    max_sources: String(maxSources)
  });
  return request<MemoryEvidenceMapRead>(`/memory/evidence-map?${params.toString()}`);
}

export function startMemoryCompilation(data: { project_id: string; bundle_id?: string }) {
  return request<MemoryCompilationRead>('/memory/compile', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export function startMemoryGraphExtraction(data: {
  project_id: string;
  memory_record_id: string;
  provider_config_id?: string;
  reasoning_effort?: 'low' | 'medium' | 'high' | 'extra' | 'max';
}) {
  return request<MemoryGraphExtractionRead>('/memory/graph-extractions', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export function getMemoryCompilation(compilationRunId: string) {
  return request<MemoryCompilationRead>(`/memory/compilations/${compilationRunId}`);
}

export function approveMemory(memoryId: string) {
  return request<MemoryRead>(`/memory/${memoryId}/approve`, { method: 'POST' });
}

export function reviewMemoryGraphItem(
  memoryId: string,
  data: {
    item_id: string;
    decision: 'accepted' | 'rejected';
    decision_note?: string;
  }
) {
  return request<MemoryGraphReviewDecisionRead>(`/memory/${memoryId}/graph-review`, {
    method: 'POST',
    body: JSON.stringify(data)
  });
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
  return request<TeamRead>('/teams', { method: 'POST', body: JSON.stringify(data) });
}

export function listTeams() {
  return request<TeamListResponse>('/teams');
}

export function getTeam(id: string) {
  return request<TeamRead>(`/teams/${id}`);
}

export function updateTeam(id: string, data: { name?: string }) {
  return request<TeamRead>(`/teams/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export function deleteTeam(id: string) {
  return request<void>(`/teams/${id}`, { method: 'DELETE' });
}

export function addTeamMember(teamId: string, data: { user_id: string; role?: string }) {
  return request<TeamMemberRead>(`/teams/${teamId}/members`, {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export function removeTeamMember(teamId: string, userId: string) {
  return request<void>(`/teams/${teamId}/members/${userId}`, { method: 'DELETE' });
}

// Organizations
export interface OrganizationRead {
  id: string;
  slug: string;
  name: string;
}

export interface OrganizationMemberRead {
  id: string;
  display_name: string;
  email: string;
  role: 'owner' | 'admin' | 'member';
  is_billing_owner: boolean;
}

export interface OrganizationMemberRemovalRead {
  user_id: string;
  active_org: OrganizationRead;
  personal_workspace_created: boolean;
}

export interface OrganizationEntitlementRead {
  org_id: string;
  plan: string;
  subscription_status: string;
  source: 'organization' | 'legacy' | 'starter';
  seat_limit: number;
  active_member_count: number;
  available_seats: number;
  seat_overage_count: number;
  capacity_enforced: boolean;
  project_limit: number;
  monthly_workflow_limit: number;
  monthly_assistant_limit: number;
  monthly_indexing_limit: number;
  is_billing_owner: boolean;
}

export function createOrganization(data: { name: string; slug: string }) {
  return request<OrganizationRead>('/organizations', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export function listOrganizations() {
  return request<OrganizationRead[]>('/organizations');
}

export function listOrganizationMembers() {
  return request<OrganizationMemberRead[]>('/organizations/current/members');
}

export function updateOrganizationMemberRole(userId: string, role: OrganizationMemberRead['role']) {
  return request<OrganizationMemberRead>(`/organizations/current/members/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify({ role })
  });
}

export function transferOrganizationBillingOwner(userId: string) {
  return request<OrganizationMemberRead>('/organizations/current/billing-owner', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId })
  });
}

export function removeOrganizationMember(userId: string) {
  return request<OrganizationMemberRemovalRead>(`/organizations/current/members/${userId}`, {
    method: 'DELETE'
  });
}

export function getOrganizationEntitlements() {
  return request<OrganizationEntitlementRead>('/organizations/current/entitlements');
}

export function switchOrganization(orgId: string) {
  return request<CurrentUser>('/organizations/switch', {
    method: 'POST',
    body: JSON.stringify({ org_id: orgId })
  });
}

// Provider Configuration
export interface ProviderConfig {
  id: string;
  user_id: string;
  provider_type: 'openai' | 'anthropic';
  provider_id: string;
  api_key: string;
  api_url: string | null;
  model: string;
  label: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProviderConfigCreate {
  provider_type: 'openai' | 'anthropic';
  provider_id?: string;
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
  code?: string | null;
}

export interface ProviderModelInfo {
  id: string;
  name?: string | null;
  owned_by?: string | null;
}

export interface ProviderModelsResult {
  models: ProviderModelInfo[];
  discovery_mode: 'supported' | 'manual' | 'unsupported';
  message?: string | null;
}

export interface PiCatalogProvider {
  id: string;
  name: string;
  base_url?: string | null;
}

export interface PiCatalogModel {
  id: string;
  name: string;
  provider: string;
  api: string;
  base_url?: string | null;
  reasoning: boolean;
  input: string[];
  context_window: number;
  max_tokens: number;
  cost: Record<string, number>;
}

export interface PiModelCatalog {
  source: 'pi-ai' | string;
  version: string;
  providers: PiCatalogProvider[];
  models: PiCatalogModel[];
}

export interface PiRuntimeContract {
  version: string;
  sandbox: {
    profile: string;
    hostTools: string;
    network: string;
    maxToolInputBytes: number;
    maxToolObservationBytes: number;
  };
  extensions: string[];
  skills: Array<{
    name: string;
    description: string;
    version?: string | null;
    resources?: string[];
  }>;
  tool_count: number;
  parallel_tool_count: number;
  mcp_servers?: Array<{ name: string; transport: string; trusted_mutations: boolean }>;
}

// Chat
export interface ChatMessageRead {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string | null;
  runtime_run_id?: string | null;
  attachments?: ChatMessageAttachmentRead[];
}

export interface ChatMessageAttachmentRead {
  id: string;
  assistant_attachment_id: string | null;
  document_id: string | null;
  name: string;
  kind: 'file' | 'image';
  mime_type: string;
  size: number;
  extraction_status: 'extracted' | 'empty' | 'unsupported' | 'failed';
  extraction_error: string | null;
}

export interface ChatConversationRead {
  id: string;
  project_id: string | null;
  title: string | null;
  is_pinned?: boolean;
  created_at: string | null;
}

export interface ChatHistoryRead {
  items: ChatMessageRead[];
  total: number;
}

export interface ChatConversationForkRead {
  conversation: ChatConversationRead;
  items: ChatMessageRead[];
  total: number;
}

export function listChatConversations(projectId?: string) {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
  return request<ChatConversationRead[]>(`/chat/conversations${query}`);
}

export function getChatConversationMessages(conversationId: string) {
  return request<ChatHistoryRead>(`/chat/conversations/${conversationId}/messages`);
}

export function forkChatConversation(conversationId: string, checkpointMessageId: string) {
  return request<ChatConversationForkRead>(`/chat/conversations/${conversationId}/fork`, {
    method: 'POST',
    body: JSON.stringify({ checkpoint_message_id: checkpointMessageId })
  });
}

export function renameChatConversation(conversationId: string, title: string) {
  return request<ChatConversationRead>(`/chat/conversations/${conversationId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title })
  });
}

export function setChatConversationPinned(conversationId: string, isPinned: boolean) {
  return request<ChatConversationRead>(`/chat/conversations/${conversationId}`, {
    method: 'PATCH',
    body: JSON.stringify({ is_pinned: isPinned })
  });
}

export function deleteChatConversation(conversationId: string) {
  return request<void>(`/chat/conversations/${conversationId}`, {
    method: 'DELETE'
  });
}

export function listProviderConfigs() {
  return request<{ data: ProviderConfig[] }>('/auth/me/providers');
}

export function getPiModelCatalog() {
  return request<{ data: PiModelCatalog }>('/auth/me/providers/catalog');
}

export function getPiRuntimeContract() {
  return request<{ data: PiRuntimeContract }>('/auth/me/providers/runtime');
}

export function createProviderConfig(payload: ProviderConfigCreate) {
  return request<{ data: ProviderConfig }>('/auth/me/providers', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function updateProviderConfig(id: string, payload: Partial<ProviderConfigCreate>) {
  return request<{ data: ProviderConfig }>(`/auth/me/providers/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload)
  });
}

export function deleteProviderConfig(id: string) {
  return request<{ data: { deleted: boolean } }>(`/auth/me/providers/${id}`, { method: 'DELETE' });
}

export type TestProviderConnectionPayload =
  | { config_id: string }
  | {
      provider_type: string;
      provider_id?: string;
      api_key: string;
      api_url?: string;
      model: string;
    };

export function testProviderConnection(payload: TestProviderConnectionPayload) {
  if ('config_id' in payload) {
    return request<{ data: TestConnectionResult }>(
      `/auth/me/providers/test?config_id=${encodeURIComponent(payload.config_id)}`,
      { method: 'POST' }
    );
  }
  return request<{ data: TestConnectionResult }>('/auth/me/providers/test', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export type ListProviderModelsPayload =
  | { config_id: string }
  | {
      provider_type: 'openai' | 'anthropic';
      provider_id?: string;
      api_key: string;
      api_url?: string;
    };

export function listProviderModels(payload: ListProviderModelsPayload) {
  return request<{ data: ProviderModelsResult }>('/auth/me/providers/models', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

// Business webhooks
export type WebhookEventType =
  | 'radar.notice.matched'
  | 'radar.notice.saved'
  | 'radar.notice.converted';
export type WebhookDeliveryStatus = 'pending' | 'delivering' | 'delivered' | 'failed';

export interface WebhookEndpointRead {
  id: string;
  name: string;
  target_url: string;
  events: WebhookEventType[];
  is_active: boolean;
  signing_secret_hint: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface WebhookEndpointCreateResult {
  endpoint: WebhookEndpointRead;
  signing_secret: string;
}

export interface WebhookDeliveryRead {
  id: string;
  endpoint_id: string;
  endpoint_name: string;
  event_type: string;
  status: WebhookDeliveryStatus;
  attempt_count: number;
  max_attempts: number;
  available_at: string | null;
  last_http_status: number | null;
  last_error_code: string | null;
  delivered_at: string | null;
  created_at: string | null;
  payload: Record<string, unknown>;
}

export interface WebhookOverviewRead {
  summary: {
    active_endpoint_count: number;
    delivery_count: number;
    failed_delivery_count: number;
    pending_delivery_count: number;
  };
  supported_events: WebhookEventType[];
  endpoints: WebhookEndpointRead[];
  deliveries: WebhookDeliveryRead[];
}

export function getWebhookOverview() {
  return request<WebhookOverviewRead>('/webhooks/overview');
}

export function createWebhookEndpoint(payload: {
  name: string;
  target_url: string;
  events: WebhookEventType[];
}) {
  return request<WebhookEndpointCreateResult>('/webhooks/endpoints', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function updateWebhookEndpoint(
  endpointId: string,
  payload: Partial<{
    name: string;
    target_url: string;
    events: WebhookEventType[];
    is_active: boolean;
  }>
) {
  return request<WebhookEndpointRead>(`/webhooks/endpoints/${endpointId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  });
}

export function deleteWebhookEndpoint(endpointId: string) {
  return request<void>(`/webhooks/endpoints/${endpointId}`, { method: 'DELETE' });
}

export function rotateWebhookSecret(endpointId: string) {
  return request<WebhookEndpointCreateResult>(`/webhooks/endpoints/${endpointId}/rotate-secret`, {
    method: 'POST'
  });
}

export function testWebhookEndpoint(endpointId: string) {
  return request<{ delivery: WebhookDeliveryRead }>(`/webhooks/endpoints/${endpointId}/test`, {
    method: 'POST'
  });
}

export function retryWebhookDelivery(deliveryId: string) {
  return request<{ delivery: WebhookDeliveryRead }>(`/webhooks/deliveries/${deliveryId}/retry`, {
    method: 'POST'
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
  return request<InvitationRead>('/invitations', { method: 'POST', body: JSON.stringify(data) });
}

export function listInvitations() {
  return request<InvitationRead[]>('/invitations');
}

export function revokeInvitation(id: string) {
  return request<void>(`/invitations/${id}`, { method: 'DELETE' });
}
