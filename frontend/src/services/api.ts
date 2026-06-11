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
  method?: "DELETE" | "GET" | "POST";
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
}

export interface KnowledgeBaseListResponse {
  items: KnowledgeBaseItem[];
}

export interface KnowledgeDocumentItem {
  id: number;
  knowledge_base_id: string;
  title: string;
  source_type: string;
  status: string;
  vector_index_status: string;
  vector_chunk_count: number;
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

export function fetchKnowledgeChunks(
  knowledgeBaseId: string,
  documentId: number
): Promise<KnowledgeChunkListResponse> {
  return request<KnowledgeChunkListResponse>({
    url: `/api/v1/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/chunks`
  });
}

export function fetchIngestionTasks(): Promise<IngestionTaskListResponse> {
  return request<IngestionTaskListResponse>({ url: "/api/v1/ingestion/tasks" });
}

export function fetchIngestionTaskNodes(taskId: number): Promise<IngestionTaskNodeListResponse> {
  return request<IngestionTaskNodeListResponse>({ url: `/api/v1/ingestion/tasks/${taskId}/nodes` });
}

export function fetchChatBootstrap(): Promise<ChatBootstrapResponse> {
  return request<ChatBootstrapResponse>({ url: "/api/v1/chat/bootstrap" });
}

export function sendChatMessage(sessionId: string, message: string): Promise<ChatMessageResponse> {
  return request<ChatMessageResponse>({
    url: "/api/v1/chat/messages",
    method: "POST",
    data: { session_id: sessionId, message }
  });
}

export async function streamChatMessage(
  sessionId: string,
  message: string,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {})
    },
    body: JSON.stringify({ session_id: sessionId, message }),
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

export function fetchSessionMessages(sessionId: string): Promise<ConversationMessageListResponse> {
  return request<ConversationMessageListResponse>({ url: `/api/v1/sessions/${sessionId}/messages` });
}
