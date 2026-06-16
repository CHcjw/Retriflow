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
  vector_indexed_at: string;
  created_at: string;
}

export interface KnowledgeDocumentListResponse {
  items: KnowledgeDocumentItem[];
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
  node_type: string;
  node_order: number;
  success: boolean;
  message: string;
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
  created_at: string;
}

export interface AdminUserCreateRequest {
  username: string;
  password: string;
  role: string;
}

export interface AdminUserListResponse {
  items: AdminUserItem[];
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
  title: string;
  owner_id: string;
  owner_username: string;
  message_count: number;
  latest_message_at: string;
  duration_ms: number;
  latest_messages: AdminTraceMessageItem[];
}

export interface AdminTraceListResponse {
  items: AdminTraceSessionItem[];
}

export interface AdminTraceDetailResponse extends AdminTraceSessionItem {
  messages: AdminTraceMessageItem[];
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
  assistant_message: string;
  sources: ChatSourceItem[];
  workflow: ChatWorkflow;
  mcp_calls: ChatMcpCallItem[];
}

export interface ConversationMessageItem {
  id: number;
  session_id: string;
  role: "assistant" | "user";
  content: string;
  created_at: string;
}

export interface ConversationMessageListResponse {
  items: ConversationMessageItem[];
}

export interface ChatStreamHandlers {
  onWorkflow?: (workflow: ChatWorkflow) => void | Promise<void>;
  onSources?: (sources: ChatSourceItem[]) => void | Promise<void>;
  onMcpCalls?: (mcpCalls: ChatMcpCallItem[]) => void | Promise<void>;
  onDelta?: (delta: string) => void | Promise<void>;
  onFinal?: (payload: ChatFinalEvent) => void | Promise<void>;
  onDone?: (sessionId: string) => void | Promise<void>;
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
  chunkStrategy?: string;
  chunkSize?: number;
  chunkOverlap?: number;
  recursiveSeparators?: string[];
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

export function createKnowledgeBase(name: string): Promise<KnowledgeBaseItem> {
  return request<KnowledgeBaseItem>({
    url: "/api/v1/knowledge-bases",
    method: "POST",
    data: { name }
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
      chunk_strategy: options?.chunkStrategy ?? "auto",
      chunk_size: options?.chunkSize ?? 600,
      chunk_overlap: options?.chunkOverlap ?? 120,
      recursive_separators: options?.recursiveSeparators ?? []
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
  formData.append("chunk_strategy", options?.chunkStrategy ?? "auto");
  formData.append("chunk_size", String(options?.chunkSize ?? 600));
  formData.append("chunk_overlap", String(options?.chunkOverlap ?? 120));
  if (options?.recursiveSeparators && options.recursiveSeparators.length > 0) {
    formData.append("recursive_separators_text", options.recursiveSeparators.join("\n"));
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
      chunk_strategy: options?.chunkStrategy ?? "auto",
      chunk_size: options?.chunkSize ?? 600,
      chunk_overlap: options?.chunkOverlap ?? 120,
      recursive_separators: options?.recursiveSeparators ?? []
    }
  });
}

export function deleteKnowledgeDocument(knowledgeBaseId: string, documentId: number): Promise<void> {
  return request<void>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/documents/${documentId}`,
    method: "DELETE"
  });
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
  enabled: boolean
): Promise<KnowledgeChunkItem> {
  return request<KnowledgeChunkItem>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/chunks/${chunkId}`,
    method: "PATCH",
    data: { enabled }
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

export function fetchIngestionTasks(): Promise<IngestionTaskListResponse> {
  return request<IngestionTaskListResponse>({ url: "/api/v1/ingestion/tasks" });
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
  return request<AdminUserListResponse>({ url: "/api/v1/admin/users" });
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

export function fetchAdminTraces(): Promise<AdminTraceListResponse> {
  return request<AdminTraceListResponse>({ url: "/api/v1/admin/traces" });
}

export function fetchAdminTraceDetail(sessionId: string): Promise<AdminTraceDetailResponse> {
  return request<AdminTraceDetailResponse>({ url: `/api/v1/admin/traces/${sessionId}` });
}

export function fetchAdminSettings(): Promise<AdminSettingListResponse> {
  return request<AdminSettingListResponse>({ url: "/api/v1/admin/settings" });
}

export function fetchAdminIntentNodes(): Promise<AdminIntentNodeListResponse> {
  return request<AdminIntentNodeListResponse>({ url: "/api/v1/admin/intent-nodes" });
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
