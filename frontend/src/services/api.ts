import axios, { AxiosError } from "axios";

const API_BASE_URL = import.meta.env.VITE_RETRIFLOW_API_BASE_URL ?? "";
const UNAUTHORIZED_EVENT = "retriflow:unauthorized";
let accessToken = "";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000
});

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      accessToken = "";
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
      }
    }
    return Promise.reject(error);
  }
);

export function setAccessToken(token: string) {
  accessToken = token.trim();
}

export function getUnauthorizedEventName(): string {
  return UNAUTHORIZED_EVENT;
}

function toRequestError(error: unknown): Error {
  if (error instanceof AxiosError) {
    const message =
      typeof error.response?.data === "object" &&
      error.response?.data !== null &&
      "detail" in error.response.data &&
      typeof error.response.data.detail === "string"
        ? error.response.data.detail
        : error.message;
    return new Error(message);
  }

  return error instanceof Error ? error : new Error("Unknown request error");
}

async function request<T>(config: {
  url: string;
  method?: "DELETE" | "GET" | "PATCH" | "POST" | "PUT";
  data?: FormData | Record<string, unknown>;
  headers?: Record<string, string>;
}): Promise<T> {
  try {
    const response = await apiClient.request<T>({
      url: config.url,
      method: config.method ?? "GET",
      data: config.data,
      headers: config.headers
    });
    return response.data;
  } catch (error) {
    throw toRequestError(error);
  }
}

async function requestBlob(url: string): Promise<{ blob: Blob; filename: string }> {
  try {
    const response = await apiClient.request<Blob>({
      url,
      method: "GET",
      responseType: "blob"
    });
    const disposition = response.headers["content-disposition"];
    const filename = parseContentDispositionFilename(typeof disposition === "string" ? disposition : "") || "document-source";
    return { blob: response.data, filename };
  } catch (error) {
    throw toRequestError(error);
  }
}

function parseContentDispositionFilename(disposition: string): string {
  const encodedMatch = /filename\*=UTF-8''([^;]+)/iu.exec(disposition);
  if (encodedMatch) {
    return decodeURIComponent(encodedMatch[1]);
  }
  const plainMatch = /filename="?([^";]+)"?/iu.exec(disposition);
  return plainMatch?.[1] ?? "";
}

export interface MetaResponse {
  name: string;
  version: string;
  api_prefix: string;
  frontend_name: string;
  primary_routes: string[];
  database_backend: string;
  runtime_database_backend: string;
  database_schema: string;
}

export interface AuthRegisterRequest {
  username: string;
  password: string;
  role?: string;
}

export interface AuthLoginRequest {
  username: string;
  password: string;
}

export interface AuthUser {
  id: string;
  username: string;
  role: string;
}

export interface AuthLoginResponse {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
}

export interface SessionItem {
  id: string;
  title: string;
  message_count: number;
}

export interface SessionListResponse {
  items: SessionItem[];
}

export interface KnowledgeBaseItem {
  id: string;
  name: string;
  product: string;
  document_count: number;
  embedding_model: string;
  collection_name: string;
  owner: string;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBaseListResponse {
  items: KnowledgeBaseItem[];
}

export interface KnowledgeBaseUpsertOptions {
  name: string;
  embeddingModel?: string;
  collectionName?: string;
}

export interface KnowledgeDocumentItem {
  id: number;
  knowledge_base_id: string;
  title: string;
  source_type: string;
  processing_mode: string;
  status: string;
  enabled: boolean;
  vector_index_status: string;
  vector_chunk_count: number;
  document_type: string;
  size_label: string;
  source_uri: string;
  vector_indexed_at: string;
  created_at: string;
}

export interface KnowledgeDocumentListResponse {
  items: KnowledgeDocumentItem[];
}

export interface KnowledgeDocumentPreviewResponse {
  id: number;
  knowledge_base_id: string;
  title: string;
  source_type: string;
  content: string;
  source_uri: string;
  created_at: string;
}

export interface KnowledgeChunkItem {
  id: number;
  knowledge_base_id: string;
  document_id: number;
  chunk_index: number;
  content: string;
  char_count: number;
  enabled: boolean;
  strategy: string;
  document_type: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface KnowledgeChunkListResponse {
  items: KnowledgeChunkItem[];
}

export interface KnowledgeChunkUpdatePayload {
  enabled?: boolean;
  content?: string;
}

export interface IngestionTaskItem {
  id: number;
  knowledge_base_id: string;
  document_id: number;
  source_type: string;
  status: string;
  chunk_count: number;
  message: string;
  created_at: string;
}

export interface IngestionTaskListResponse {
  items: IngestionTaskItem[];
}

export interface IngestionTaskNodeItem {
  id: number;
  task_id: number;
  node_id: string;
  node_type: string;
  node_order: number;
  success: boolean;
  status: string;
  message: string;
  error_message: string;
  output: Record<string, unknown>;
  duration_ms: number;
  created_at: string;
}

export interface IngestionTaskNodeListResponse {
  items: IngestionTaskNodeItem[];
}

export interface IngestionPipelineNodeConfig {
  node_id: string;
  node_type: string;
  next_node_id: string;
  condition: string;
  config: Record<string, unknown>;
}

export interface IngestionPipelineItem {
  id: number;
  name: string;
  description: string;
  nodes: IngestionPipelineNodeConfig[];
  node_count: number;
  owner: string;
  created_at: string;
  updated_at: string;
}

export interface IngestionPipelineCreateRequest {
  name: string;
  description: string;
  nodes: IngestionPipelineNodeConfig[];
  owner?: string;
}

export interface IngestionPipelineListResponse {
  items: IngestionPipelineItem[];
}

export interface AdminUserItem {
  id: string;
  username: string;
  role: string;
  avatar_url: string;
  created_at: string;
}

export interface AdminUserCreateRequest {
  username: string;
  password: string;
  role: string;
  avatar_url?: string;
}

export interface AdminUserUpdateRequest {
  username?: string;
  role?: string;
  avatar_url?: string;
}

export interface AdminUserPasswordChangeRequest {
  old_password: string;
  new_password: string;
}

export interface AdminUserListResponse {
  items: AdminUserItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminTraceMessageItem {
  id: number;
  role: string;
  content_preview: string;
  created_at: string;
  duration_ms: number;
}

export interface AdminTraceSessionItem {
  id: string;
  trace_id: string;
  task_id: string;
  status: string;
  title: string;
  owner_id: string;
  owner_username: string;
  message_count: number;
  started_at: string;
  latest_message_at: string;
  duration_ms: number;
  latest_messages: AdminTraceMessageItem[];
}

export interface AdminTraceListResponse {
  items: AdminTraceSessionItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminMessageFeedbackItem {
  id: number;
  message_id: number;
  session_id: string;
  user_id: string;
  username: string;
  vote: 1 | -1;
  reason: string;
  comment: string;
  message_preview: string;
  created_at: string;
  updated_at: string;
}

export interface AdminMessageFeedbackListResponse {
  items: AdminMessageFeedbackItem[];
}

export interface AdminTraceDetailResponse extends AdminTraceSessionItem {
  messages: AdminTraceMessageItem[];
}

export interface AdminTraceMemoryDiagnosticsResponse {
  session_id: string;
  has_summary: boolean;
  summary_preview: string;
  recent_message_count: number;
  mid_term_count: number;
  long_term_count: number;
  prompt_message_count: number;
}

export interface AdminTraceNodeItem {
  id: string;
  session_id: string;
  task_id: string;
  parent_id: string;
  name: string;
  node_type: string;
  status: string;
  input_summary: string;
  output_summary: string;
  error_message: string;
  metadata: Record<string, unknown>;
  started_at: string;
  finished_at: string;
  duration_ms: number;
}

export interface AdminTraceNodeListResponse {
  items: AdminTraceNodeItem[];
}

export interface AdminModelHealthItem {
  capability: string;
  provider_name: string;
  model: string;
  state: string;
  failure_count: number;
  success_count: number;
  opened_at: number | null;
  last_success_at: number | null;
  last_failure_at: number | null;
  last_error: string;
  last_success_duration_ms: number | null;
  last_first_packet_ms: number | null;
  half_open_in_flight: boolean;
}

export interface AdminModelHealthListResponse {
  items: AdminModelHealthItem[];
}

export interface AdminModelHealthProbeRequest {
  capability: string;
  provider_name?: string;
  model?: string;
}

export interface AdminSettingItem {
  key: string;
  value: string;
  category: string;
  sensitive: boolean;
}

export interface AdminSettingListResponse {
  items: AdminSettingItem[];
}

export interface AdminDashboardMetricCard {
  key: string;
  label: string;
  value: string;
  helper: string;
  delta: string;
}

export interface AdminDashboardSeries {
  key: string;
  label: string;
  color: string;
  values: number[];
}

export interface AdminDashboardAiPerformance {
  success_rate: number;
  completion_rate: number;
  avg_response_ms: number;
  p95_response_ms: number;
  no_answer_rate: number;
}

export interface AdminDashboardTrafficOverview {
  labels: string[];
  series: AdminDashboardSeries[];
  total_sessions: number;
  total_messages: number;
  total_active_users: number;
}

export interface AdminDashboardTrendPanel {
  key: string;
  label: string;
  unit: string;
  summary: string;
  series: AdminDashboardSeries[];
}

export interface AdminDashboardOpsInsight {
  level: string;
  category: string;
  title: string;
  message: string;
  time_label: string;
}

export interface AdminDashboardResponse {
  range: string;
  range_label: string;
  generated_at: string;
  core: AdminDashboardMetricCard[];
  ai_performance: AdminDashboardAiPerformance;
  traffic_overview: AdminDashboardTrafficOverview;
  trend_panels: AdminDashboardTrendPanel[];
  quality_snapshot: AdminDashboardMetricCard[];
  ops_efficiency: AdminDashboardMetricCard[];
  ops_insights: AdminDashboardOpsInsight[];
}

export interface AdminIntentNodeItem {
  id: string;
  name: string;
  code: string;
  level: string;
  node_type: string;
  parent_id: string;
  knowledge_base_id: string;
  collection_name: string;
  description: string;
  sample_questions: string[];
  rule_snippet: string;
  prompt_template: string;
  top_k: number | null;
  sort_order: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AdminIntentNodeUpsertRequest {
  name?: string;
  code?: string;
  level?: string;
  node_type?: string;
  parent_id?: string;
  knowledge_base_id?: string;
  collection_name?: string;
  description?: string;
  sample_questions?: string[];
  rule_snippet?: string;
  prompt_template?: string;
  top_k?: number | null;
  sort_order?: number;
  enabled?: boolean;
}

export interface AdminIntentNodeListResponse {
  items: AdminIntentNodeItem[];
}

export interface AdminIntentTreeCacheStatusResponse {
  enabled: boolean;
  available: boolean;
  exists: boolean;
  key: string;
  ttl_seconds: number | null;
  ttl_days: number;
  backend: string;
  error: string;
}

export interface AdminKeywordMappingItem {
  id: string;
  raw_keyword: string;
  target_keyword: string;
  match_type: string;
  priority: number;
  enabled: boolean;
  remark: string;
  knowledge_base_id: string;
  created_at: string;
  updated_at: string;
}

export interface AdminKeywordMappingUpsertRequest {
  raw_keyword?: string;
  target_keyword?: string;
  match_type?: string;
  priority?: number;
  enabled?: boolean;
  remark?: string;
  knowledge_base_id?: string;
}

export interface AdminKeywordMappingListResponse {
  items: AdminKeywordMappingItem[];
}

export interface ChatBootstrapResponse {
  product: string;
  capabilities: string[];
}

export interface ChatSourceItem {
  chunk_id: number;
  knowledge_base_id: string;
  document_id: number;
  document_title: string;
  content: string;
  score: number;
  source_link?: string;
  source_updated_at?: string;
}

export interface ChatWorkflow {
  name: string;
  adapter: string;
  retrieval_channels: string[];
  retrieval_count: number;
  retrieval_stage_counts: Record<string, number>;
  rewritten_queries: string[];
  rewrite_query_count: number;
  pipeline_stages: string[];
  route_mode: string;
  mcp_tool_count: number;
  deep_thinking?: boolean;
}

export interface ChatMcpCallItem {
  tool_id: string;
  arguments: Record<string, unknown>;
  content: string;
  is_error: boolean;
}

export interface ChatMessageResponse {
  session_id: string;
  assistant_message_id: number | null;
  assistant_message: string;
  sources: ChatSourceItem[];
  workflow: ChatWorkflow;
  mcp_calls: ChatMcpCallItem[];
}

export interface MessageFeedbackResponse {
  message_id: number;
  session_id: string;
  vote: 1 | -1;
  reason: string;
  comment: string;
  updated_at: string;
}

export interface ConversationMessageItem {
  id: number;
  session_id: string;
  role: "assistant" | "user";
  content: string;
  created_at: string;
  duration_ms: number;
}

export interface ConversationMessageListResponse {
  items: ConversationMessageItem[];
}

export interface ChatStreamHandlers {
  onTask?: (payload: ChatTaskEvent) => void | Promise<void>;
  onWorkflow?: (workflow: ChatWorkflow) => void | Promise<void>;
  onSources?: (sources: ChatSourceItem[]) => void | Promise<void>;
  onMcpCalls?: (mcpCalls: ChatMcpCallItem[]) => void | Promise<void>;
  onDelta?: (delta: string) => void | Promise<void>;
  onCancel?: (payload: ChatTaskEvent) => void | Promise<void>;
  onReject?: (payload: ChatRejectEvent) => void | Promise<void>;
  onFinal?: (payload: ChatFinalEvent) => void | Promise<void>;
  onDone?: (sessionId: string) => void | Promise<void>;
}

export interface ChatTaskEvent {
  task_id: string;
}

export interface ChatRejectEvent {
  message: string;
  reason?: string;
}

export interface ChatFinalEvent {
  status: string;
  mode?: "append" | "replace";
  content?: string;
  content_delta?: string;
}

async function yieldForPaint(): Promise<void> {
  await new Promise<void>((resolve) => {
    if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(() => resolve());
      return;
    }
    setTimeout(resolve, 0);
  });
}

export interface KnowledgeChunkingOptions {
  documentType?: string;
  processMode?: "chunk_strategy" | "data_channel";
  pipelineId?: number;
  chunkStrategy?: string;
  chunkSize?: number;
  chunkOverlap?: number;
  recursiveSeparators?: string[];
  chunkConfig?: Record<string, unknown>;
}

export function fetchMeta(): Promise<MetaResponse> {
  return request<MetaResponse>({ url: "/api/v1/meta" });
}

export function registerUser(payload: AuthRegisterRequest): Promise<AuthUser> {
  return request<AuthUser>({
    url: "/api/v1/auth/register",
    method: "POST",
    data: payload
  });
}

export function loginWithPassword(payload: AuthLoginRequest): Promise<AuthLoginResponse> {
  return request<AuthLoginResponse>({
    url: "/api/v1/auth/login",
    method: "POST",
    data: payload
  });
}

export function fetchCurrentUser(): Promise<AuthUser> {
  return request<AuthUser>({ url: "/api/v1/auth/me" });
}

export function fetchSessions(): Promise<SessionListResponse> {
  return request<SessionListResponse>({ url: "/api/v1/sessions" });
}

export function createSession(title: string): Promise<SessionItem> {
  return request<SessionItem>({
    url: "/api/v1/sessions",
    method: "POST",
    data: { title }
  });
}

export function deleteSession(sessionId: string): Promise<void> {
  return request<void>({
    url: `/api/v1/sessions/${sessionId}`,
    method: "DELETE"
  });
}

export function updateSession(sessionId: string, title: string): Promise<SessionItem> {
  return request<SessionItem>({
    url: `/api/v1/sessions/${sessionId}`,
    method: "PATCH",
    data: { title }
  });
}

export function fetchKnowledgeBases(): Promise<KnowledgeBaseListResponse> {
  return request<KnowledgeBaseListResponse>({ url: "/api/v1/knowledge-bases" });
}

export function createKnowledgeBase(options: string | KnowledgeBaseUpsertOptions): Promise<KnowledgeBaseItem> {
  const payload =
    typeof options === "string"
      ? { name: options }
      : {
          name: options.name,
          embedding_model: options.embeddingModel,
          collection_name: options.collectionName
        };
  return request<KnowledgeBaseItem>({
    url: "/api/v1/knowledge-bases",
    method: "POST",
    data: payload
  });
}

export function updateKnowledgeBase(
  knowledgeBaseId: string,
  options: Partial<KnowledgeBaseUpsertOptions>
): Promise<KnowledgeBaseItem> {
  return request<KnowledgeBaseItem>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}`,
    method: "PATCH",
    data: {
      name: options.name,
      embedding_model: options.embeddingModel,
      collection_name: options.collectionName
    }
  });
}

export function deleteKnowledgeBase(knowledgeBaseId: string): Promise<void> {
  return request<void>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}`,
    method: "DELETE"
  });
}

export function fetchKnowledgeDocuments(knowledgeBaseId: string): Promise<KnowledgeDocumentListResponse> {
  return request<KnowledgeDocumentListResponse>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/documents`
  });
}

export function createKnowledgeDocument(
  knowledgeBaseId: string,
  title: string,
  content: string,
  options?: KnowledgeChunkingOptions
): Promise<KnowledgeDocumentItem> {
  return request<KnowledgeDocumentItem>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/documents`,
    method: "POST",
    data: {
      title,
      source_type: "manual",
      content,
      document_type: options?.documentType ?? "manual",
      process_mode: options?.processMode ?? "chunk_strategy",
      pipeline_id: options?.pipelineId,
      chunk_strategy: options?.chunkStrategy ?? "auto",
      chunk_size: options?.chunkSize ?? 600,
      chunk_overlap: options?.chunkOverlap ?? 120,
      recursive_separators: options?.recursiveSeparators ?? [],
      chunk_config: options?.chunkConfig ?? {}
    }
  });
}

export function uploadKnowledgeDocument(
  knowledgeBaseId: string,
  file: File,
  options?: KnowledgeChunkingOptions
): Promise<KnowledgeDocumentItem> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", options?.documentType ?? "knowledge_base");
  formData.append("process_mode", options?.processMode ?? "chunk_strategy");
  if (options?.pipelineId !== undefined) {
    formData.append("pipeline_id", String(options.pipelineId));
  }
  formData.append("chunk_strategy", options?.chunkStrategy ?? "recursive");
  formData.append("chunk_size", String(options?.chunkSize ?? 600));
  formData.append("chunk_overlap", String(options?.chunkOverlap ?? 120));
  if (options?.recursiveSeparators && options.recursiveSeparators.length > 0) {
    formData.append("recursive_separators_text", options.recursiveSeparators.join("\n"));
  }
  if (options?.chunkConfig) {
    formData.append("chunk_config_json", JSON.stringify(options.chunkConfig));
  }
  return request<KnowledgeDocumentItem>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/documents/upload`,
    method: "POST",
    data: formData
  });
}

export function reindexKnowledgeDocument(
  knowledgeBaseId: string,
  documentId: number,
  options?: KnowledgeChunkingOptions
): Promise<KnowledgeDocumentItem> {
  return request<KnowledgeDocumentItem>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/reindex`,
    method: "POST",
    data: {
      document_type: options?.documentType,
      process_mode: options?.processMode ?? "chunk_strategy",
      pipeline_id: options?.pipelineId,
      chunk_strategy: options?.chunkStrategy ?? "auto",
      chunk_size: options?.chunkSize ?? 600,
      chunk_overlap: options?.chunkOverlap ?? 120,
      recursive_separators: options?.recursiveSeparators ?? [],
      chunk_config: options?.chunkConfig ?? {}
    }
  });
}

export function deleteKnowledgeDocument(knowledgeBaseId: string, documentId: number): Promise<void> {
  return request<void>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/documents/${documentId}`,
    method: "DELETE"
  });
}

export function updateKnowledgeDocument(
  knowledgeBaseId: string,
  documentId: number,
  payload: { title?: string; enabled?: boolean }
): Promise<KnowledgeDocumentItem> {
  return request<KnowledgeDocumentItem>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/documents/${documentId}`,
    method: "PATCH",
    data: payload
  });
}

export function fetchKnowledgeDocumentPreview(
  knowledgeBaseId: string,
  documentId: number
): Promise<KnowledgeDocumentPreviewResponse> {
  return request<KnowledgeDocumentPreviewResponse>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/preview`
  });
}

export function downloadKnowledgeDocumentSource(
  knowledgeBaseId: string,
  documentId: number
): Promise<{ blob: Blob; filename: string }> {
  return requestBlob(`/api/v1/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/file`);
}

export function fetchKnowledgeChunks(
  knowledgeBaseId: string,
  documentId: number
): Promise<KnowledgeChunkListResponse> {
  return request<KnowledgeChunkListResponse>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/chunks`
  });
}

export function updateKnowledgeChunk(
  knowledgeBaseId: string,
  documentId: number,
  chunkId: number,
  payload: boolean | KnowledgeChunkUpdatePayload
): Promise<KnowledgeChunkItem> {
  return request<KnowledgeChunkItem>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/chunks/${chunkId}`,
    method: "PATCH",
    data: typeof payload === "boolean" ? { enabled: payload } : payload
  });
}

export function updateKnowledgeChunks(
  knowledgeBaseId: string,
  documentId: number,
  chunkIds: number[],
  enabled: boolean
): Promise<{ updated_count: number }> {
  return request<{ updated_count: number }>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/chunks`,
    method: "PATCH",
    data: { chunk_ids: chunkIds, enabled }
  });
}

export function deleteKnowledgeChunk(knowledgeBaseId: string, documentId: number, chunkId: number): Promise<void> {
  return request<void>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/chunks/${chunkId}`,
    method: "DELETE"
  });
}

export function fetchIngestionTasks(options?: { documentId?: number }): Promise<IngestionTaskListResponse> {
  const query =
    options?.documentId !== undefined ? `?document_id=${encodeURIComponent(String(options.documentId))}` : "";
  return request<IngestionTaskListResponse>({ url: `/api/v1/ingestion/tasks${query}` });
}

export function fetchIngestionPipelines(): Promise<IngestionPipelineListResponse> {
  return request<IngestionPipelineListResponse>({ url: "/api/v1/ingestion/pipelines" });
}

export function createIngestionPipeline(
  payload: IngestionPipelineCreateRequest
): Promise<IngestionPipelineItem> {
  return request<IngestionPipelineItem>({
    url: "/api/v1/ingestion/pipelines",
    method: "POST",
    data: payload as unknown as Record<string, unknown>
  });
}

export function fetchIngestionTaskNodes(taskId: number): Promise<IngestionTaskNodeListResponse> {
  return request<IngestionTaskNodeListResponse>({ url: `/api/v1/ingestion/tasks/${taskId}/nodes` });
}

export function fetchAdminUsers(): Promise<AdminUserListResponse> {
  return request<AdminUserListResponse>({ url: "/api/v1/admin/users?page_size=100" });
}

export function fetchAdminDashboard(range = "24h"): Promise<AdminDashboardResponse> {
  return request<AdminDashboardResponse>({ url: `/api/v1/admin/dashboard?range=${encodeURIComponent(range)}` });
}

export function createAdminUser(payload: AdminUserCreateRequest): Promise<AdminUserItem> {
  return request<AdminUserItem>({
    url: "/api/v1/admin/users",
    method: "POST",
    data: payload
  });
}

export function updateAdminUserRole(userId: string, role: string): Promise<AdminUserItem> {
  return request<AdminUserItem>({
    url: `/api/v1/admin/users/${userId}/role`,
    method: "PATCH",
    data: { role }
  });
}

export function updateAdminUser(userId: string, payload: AdminUserUpdateRequest): Promise<AdminUserItem> {
  return request<AdminUserItem>({
    url: `/api/v1/admin/users/${userId}`,
    method: "PATCH",
    data: payload
  });
}

export function deleteAdminUser(userId: string): Promise<void> {
  return request<void>({
    url: `/api/v1/admin/users/${userId}`,
    method: "DELETE"
  });
}

export function changeAdminUserPassword(payload: AdminUserPasswordChangeRequest): Promise<void> {
  return request<void>({
    url: "/api/v1/admin/users/me/password",
    method: "PATCH",
    data: payload
  });
}

export interface AdminTraceQueryOptions {
  page?: number;
  pageSize?: number;
  query?: string;
  traceId?: string;
  taskId?: string;
  userQuery?: string;
  status?: "success" | "error" | "running" | "cancelled" | "empty" | "";
  startedFrom?: string;
  startedTo?: string;
}

export function fetchAdminTraces(options: AdminTraceQueryOptions = {}): Promise<AdminTraceListResponse> {
  const params = new URLSearchParams();
  if (options.page !== undefined) {
    params.set("page", String(options.page));
  }
  if (options.pageSize !== undefined) {
    params.set("page_size", String(options.pageSize));
  }
  if (options.query?.trim()) {
    params.set("q", options.query.trim());
  }
  if (options.traceId?.trim()) {
    params.set("trace_id", options.traceId.trim());
  }
  if (options.taskId?.trim()) {
    params.set("task_id", options.taskId.trim());
  }
  if (options.userQuery?.trim()) {
    params.set("user_query", options.userQuery.trim());
  }
  if (options.status) {
    params.set("status", options.status);
  }
  if (options.startedFrom?.trim()) {
    params.set("started_from", options.startedFrom.trim());
  }
  if (options.startedTo?.trim()) {
    params.set("started_to", options.startedTo.trim());
  }
  const query = params.toString();
  return request<AdminTraceListResponse>({ url: `/api/v1/admin/traces${query ? `?${query}` : ""}` });
}

export function fetchAdminMessageFeedback(): Promise<AdminMessageFeedbackListResponse> {
  return request<AdminMessageFeedbackListResponse>({ url: "/api/v1/admin/message-feedback" });
}

export function fetchAdminTraceDetail(sessionId: string): Promise<AdminTraceDetailResponse> {
  return request<AdminTraceDetailResponse>({ url: `/api/v1/admin/traces/${sessionId}` });
}

export function fetchAdminTraceMemoryDiagnostics(sessionId: string): Promise<AdminTraceMemoryDiagnosticsResponse> {
  return request<AdminTraceMemoryDiagnosticsResponse>({ url: `/api/v1/admin/traces/${sessionId}/memory` });
}

export function fetchAdminTraceNodes(sessionId: string): Promise<AdminTraceNodeListResponse> {
  return request<AdminTraceNodeListResponse>({ url: `/api/v1/admin/traces/${sessionId}/nodes` });
}

export function fetchAdminModelHealth(): Promise<AdminModelHealthListResponse> {
  return request<AdminModelHealthListResponse>({ url: "/api/v1/admin/model-health" });
}

export function probeAdminModelHealth(payload: AdminModelHealthProbeRequest): Promise<AdminModelHealthItem> {
  return request<AdminModelHealthItem>({
    url: "/api/v1/admin/model-health/probe",
    method: "POST",
    data: payload
  });
}

export function fetchAdminSettings(): Promise<AdminSettingListResponse> {
  return request<AdminSettingListResponse>({ url: "/api/v1/admin/settings" });
}

export function fetchAdminIntentNodes(): Promise<AdminIntentNodeListResponse> {
  return request<AdminIntentNodeListResponse>({ url: "/api/v1/admin/intent-nodes" });
}

export function fetchAdminIntentTreeCacheStatus(): Promise<AdminIntentTreeCacheStatusResponse> {
  return request<AdminIntentTreeCacheStatusResponse>({ url: "/api/v1/admin/intent-tree-cache" });
}

export function clearAdminIntentTreeCache(): Promise<AdminIntentTreeCacheStatusResponse> {
  return request<AdminIntentTreeCacheStatusResponse>({
    url: "/api/v1/admin/intent-tree-cache",
    method: "DELETE"
  });
}

export function createAdminIntentNode(payload: AdminIntentNodeUpsertRequest): Promise<AdminIntentNodeItem> {
  return request<AdminIntentNodeItem>({
    url: "/api/v1/admin/intent-nodes",
    method: "POST",
    data: payload as Record<string, unknown>
  });
}

export function updateAdminIntentNode(
  nodeId: string,
  payload: AdminIntentNodeUpsertRequest
): Promise<AdminIntentNodeItem> {
  return request<AdminIntentNodeItem>({
    url: `/api/v1/admin/intent-nodes/${nodeId}`,
    method: "PATCH",
    data: payload as Record<string, unknown>
  });
}

export function deleteAdminIntentNode(nodeId: string): Promise<void> {
  return request<void>({
    url: `/api/v1/admin/intent-nodes/${nodeId}`,
    method: "DELETE"
  });
}

export function fetchAdminKeywordMappings(): Promise<AdminKeywordMappingListResponse> {
  return request<AdminKeywordMappingListResponse>({ url: "/api/v1/admin/keyword-mappings" });
}

export function createAdminKeywordMapping(
  payload: AdminKeywordMappingUpsertRequest
): Promise<AdminKeywordMappingItem> {
  return request<AdminKeywordMappingItem>({
    url: "/api/v1/admin/keyword-mappings",
    method: "POST",
    data: payload as Record<string, unknown>
  });
}

export function updateAdminKeywordMapping(
  mappingId: string,
  payload: AdminKeywordMappingUpsertRequest
): Promise<AdminKeywordMappingItem> {
  return request<AdminKeywordMappingItem>({
    url: `/api/v1/admin/keyword-mappings/${mappingId}`,
    method: "PATCH",
    data: payload as Record<string, unknown>
  });
}

export function deleteAdminKeywordMapping(mappingId: string): Promise<void> {
  return request<void>({
    url: `/api/v1/admin/keyword-mappings/${mappingId}`,
    method: "DELETE"
  });
}

export function fetchChatBootstrap(): Promise<ChatBootstrapResponse> {
  return request<ChatBootstrapResponse>({ url: "/api/v1/chat/bootstrap" });
}

export function sendChatMessage(sessionId: string, message: string, deepThinking = false): Promise<ChatMessageResponse> {
  return request<ChatMessageResponse>({
    url: "/api/v1/chat/messages",
    method: "POST",
    data: { session_id: sessionId, message, deep_thinking: deepThinking }
  });
}

export function submitMessageFeedback(
  messageId: number,
  vote: 1 | -1,
  payload: { reason?: string; comment?: string } = {}
): Promise<MessageFeedbackResponse> {
  return request<MessageFeedbackResponse>({
    url: `/api/v1/chat/messages/${messageId}/feedback`,
    method: "POST",
    data: {
      vote,
      reason: payload.reason ?? "",
      comment: payload.comment ?? ""
    }
  });
}

export function cancelChatStreamTask(taskId: string): Promise<{ task_id: string; status: string }> {
  return request<{ task_id: string; status: string }>({
    url: `/api/v1/chat/stream/${encodeURIComponent(taskId)}/cancel`,
    method: "POST",
    data: {}
  });
}

export async function streamChatMessage(
  sessionId: string,
  message: string,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
  deepThinking = false
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {})
    },
    body: JSON.stringify({ session_id: sessionId, message, deep_thinking: deepThinking }),
    signal
  });

  if (!response.ok || !response.body) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
    }
    throw new Error(`Request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const rawEvent of events) {
      const lines = rawEvent.split("\n");
      const eventName = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
      const data = lines
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .join("\n");

      if (!eventName || !data) {
        continue;
      }

      if (eventName === "task") {
        await handlers.onTask?.(JSON.parse(data) as ChatTaskEvent);
      }
      if (eventName === "workflow") {
        await handlers.onWorkflow?.(JSON.parse(data) as ChatWorkflow);
      }
      if (eventName === "sources") {
        await handlers.onSources?.(JSON.parse(data) as ChatSourceItem[]);
      }
      if (eventName === "mcp_calls") {
        await handlers.onMcpCalls?.(JSON.parse(data) as ChatMcpCallItem[]);
      }
      if (eventName === "delta") {
        await handlers.onDelta?.((JSON.parse(data) as { content: string }).content);
        await yieldForPaint();
      }
      if (eventName === "cancel") {
        await handlers.onCancel?.(JSON.parse(data) as ChatTaskEvent);
      }
      if (eventName === "reject") {
        await handlers.onReject?.(JSON.parse(data) as ChatRejectEvent);
      }
      if (eventName === "final") {
        await handlers.onFinal?.(JSON.parse(data) as ChatFinalEvent);
        await yieldForPaint();
      }
      if (eventName === "done") {
        await handlers.onDone?.((JSON.parse(data) as { session_id: string }).session_id);
      }
    }
  }
}

export interface KnowledgeBaseRouteProfile {
  knowledge_base_id: string;
  profile_text: string;
  sample_questions: string[];
  keywords: string[];
  updated_at: string;
}

export interface KnowledgeBaseRouteProfileUpdateRequest {
  profile_text: string;
  sample_questions: string[];
  keywords: string[];
}

export function fetchRouteProfile(knowledgeBaseId: string): Promise<KnowledgeBaseRouteProfile> {
  return request<KnowledgeBaseRouteProfile>({ url: `/api/v1/knowledge-bases/${knowledgeBaseId}/route-profile` });
}

export function updateRouteProfile(
  knowledgeBaseId: string,
  data: KnowledgeBaseRouteProfileUpdateRequest
): Promise<KnowledgeBaseRouteProfile> {
  return request<KnowledgeBaseRouteProfile>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/route-profile`,
    method: "PUT",
    data: data as unknown as Record<string, unknown>
  });
}

export function fetchSessionMessages(sessionId: string): Promise<ConversationMessageListResponse> {
  return request<ConversationMessageListResponse>({ url: `/api/v1/sessions/${sessionId}/messages` });
}
