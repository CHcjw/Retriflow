<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, useTemplateRef, watch } from "vue";
import { useRouter } from "vue-router";

import AdminChunkEditModal from "../components/admin/chunks/AdminChunkEditModal.vue";
import AdminChunkTable from "../components/admin/chunks/AdminChunkTable.vue";
import AdminNotice from "../components/admin/common/AdminNotice.vue";
import AdminToastStack from "../components/admin/common/AdminToastStack.vue";
import AdminDashboardPanel from "../components/admin/dashboard/AdminDashboardPanel.vue";
import AdminDocumentPreviewModal from "../components/admin/documents/AdminDocumentPreviewModal.vue";
import AdminDocumentTable from "../components/admin/documents/AdminDocumentTable.vue";
import AdminDocumentUploadModal from "../components/admin/documents/AdminDocumentUploadModal.vue";
import AdminIntentNodeModal from "../components/admin/intent/AdminIntentNodeModal.vue";
import AdminIntentPanel from "../components/admin/intent/AdminIntentPanel.vue";
import AdminKeywordMappingModal from "../components/admin/keyword/AdminKeywordMappingModal.vue";
import AdminKeywordMappingsPanel from "../components/admin/keyword/AdminKeywordMappingsPanel.vue";
import AdminKnowledgeBaseModal from "../components/admin/knowledge/AdminKnowledgeBaseModal.vue";
import AdminKnowledgeBaseTable from "../components/admin/knowledge/AdminKnowledgeBaseTable.vue";
import AdminPipelineEditorModal from "../components/admin/pipeline/AdminPipelineEditorModal.vue";
import AdminPipelineNodesModal from "../components/admin/pipeline/AdminPipelineNodesModal.vue";
import AdminPipelineTables from "../components/admin/pipeline/AdminPipelineTables.vue";
import AdminPipelineTaskModal from "../components/admin/pipeline/AdminPipelineTaskModal.vue";
import AdminSampleQuestionsPanel from "../components/admin/samples/AdminSampleQuestionsPanel.vue";
import AdminMcpStatusPanel from "../components/admin/settings/AdminMcpStatusPanel.vue";
import AdminSettingsPanel from "../components/admin/settings/AdminSettingsPanel.vue";
import AdminTracePanel from "../components/admin/trace/AdminTracePanel.vue";
import AdminUserModal from "../components/admin/users/AdminUserModal.vue";
import AdminUsersPanel from "../components/admin/users/AdminUsersPanel.vue";
import { useAdminFormatters } from "../composables/admin/common/useAdminFormatters";
import { useAdminNavigation, type AdminTab } from "../composables/admin/common/useAdminNavigation";
import { useAdminPagination } from "../composables/admin/common/useAdminPagination";
import { useAdminToasts } from "../composables/admin/common/useAdminToasts";
import {
  buildUploadChunkConfig,
  parseUploadRecursiveSeparators,
  serializeUploadRecursiveSeparators
} from "../composables/admin/documents/useAdminUploadConfig";
import { useAdminDashboardSummary } from "../composables/admin/dashboard/useAdminDashboardSummary";
import { useAdminIntentNodeForm } from "../composables/admin/intent/useAdminIntentNodeForm";
import { useAdminIntentTree } from "../composables/admin/intent/useAdminIntentTree";
import { useAdminKeywordMappingForm } from "../composables/admin/keyword/useAdminKeywordMappingForm";
import { useAdminKnowledgeBaseForm } from "../composables/admin/knowledge/useAdminKnowledgeBaseForm";
import {
  pipelineNodeTypeOptions,
  stringifyPipelineNodes,
  useAdminPipelineEditor
} from "../composables/admin/pipeline/useAdminPipelineEditor";
import { useAdminPipelineTaskForm } from "../composables/admin/pipeline/useAdminPipelineTaskForm";
import { useAdminUserForm } from "../composables/admin/users/useAdminUserForm";
import { useRetriFlowAdmin } from "../composables/useRetriFlowAdmin";
import {
  deleteKnowledgeChunk,
  downloadKnowledgeDocumentSource,
  fetchKnowledgeDocumentPreview,
  updateKnowledgeChunk,
  updateKnowledgeChunks,
  type KnowledgeDocumentPreviewResponse
} from "../services/knowledgeApi";
import { type IngestionPipelineNodeConfig } from "../services/pipelineApi";
import { useAuthStore } from "../stores/auth";

type KnowledgeStage = "chunks" | "documents" | "knowledge-bases";
type SettingCard = {
  title: string;
  items: Array<{ label: string; value: string }>;
};

const router = useRouter();
const authStore = useAuthStore();
const {
  chunkMetadataSummary,
  documentTypeLabel,
  formatDate,
  formatDuration,
  processingModeLabel,
  sourceLabel,
  statusClass,
  statusLabel
} = useAdminFormatters();

const {
  loading,
  documentLoading,
  chunkLoading,
  taskNodeLoading,
  uploadLoading,
  reindexLoading,
  reindexingDocumentId,
  error,
  infoMessage,
  knowledgeBases,
  selectedKnowledgeBase,
  selectedKnowledgeBaseId,
  documents,
  selectedDocument,
  selectedDocumentId,
  chunks,
  ingestionPipelines,
  ingestionTasks,
  selectedDocumentTask,
  ingestionTaskNodes,
  adminUsers,
  adminDashboard,
  adminIntentNodes,
  adminKeywordMappings,
  adminSampleQuestions,
  adminTraces,
  adminTraceTotal,
  adminTracePage,
  adminTracePageSize,
  adminTraceId,
  selectedAdminTrace,
  selectedAdminTraceNodes,
  adminSettings,
  canManageKnowledge,
  dashboardRange,
  readonlyNotice,
  relatedTask,
  uploadProcessMode,
  uploadPipelineId,
  uploadChunkStrategy,
  uploadChunkSize,
  uploadChunkOverlap,
  uploadStructureMaxChars,
  uploadStructureMinChars,
  uploadRecursiveSeparatorsText,
  documentProcessMode,
  documentPipelineId,
  documentChunkStrategy,
  documentChunkSize,
  documentChunkOverlap,
  documentStructureMaxChars,
  documentStructureMinChars,
  documentRecursiveSeparatorsText,
  documentTypeOptions,
  chunkStrategyOptions,
  uploadChunkSummary,
  uploadShowChunkSizeControls,
  uploadAutoStrategyRecommendation,
  uploadRecursiveSeparatorSummary,
  uploadShowRecursiveSeparatorControls,
  uploadShowSemanticNotice,
  addKnowledgeBase,
  removeKnowledgeBase,
  selectKnowledgeBase,
  selectDocument,
  removeDocument,
  loadDocuments,
  loadChunks,
  createPipeline,
  updatePipeline,
  removePipeline,
  loadTaskNodes,
  refreshKnowledgeData,
  uploadDocument,
  saveKnowledgeBase,
  saveDocument,
  saveChunk,
  syncDocumentEditorDefaults,
  reindexDocumentWithOptions,
  reindexDocument,
  routeProfileLoading,
  routeProfile,
  saveRouteProfile,
  addKeyword,
  removeKeyword,
  loadSampleQuestions,
  createSampleQuestion,
  updateSampleQuestion,
  removeSampleQuestionConfig,
  changeUserRole,
  saveUser,
  removeUser,
  changeOwnPassword,
  createUser,
  loadDashboard,
  createIntentNode,
  updateIntentNode,
  removeIntentNode,
  createKeywordMapping,
  updateKeywordMapping,
  removeKeywordMapping,
  loadAdminTraces,
  searchAdminTraces,
  loadTraceDetail,
  clearTraceDetail
} = useRetriFlowAdmin();

const knowledgeSearch = shallowRef("");
const adminSearchInput = useTemplateRef<HTMLInputElement>("adminSearchInput");
const documentSearch = shallowRef("");
const documentStatusFilter = shallowRef("all");
const chunkStatusFilter = shallowRef("all");
const selectedChunkIds = ref<number[]>([]);
const selectedUploadFileName = shallowRef("");
const selectedUploadFile = shallowRef<File | null>(null);
const showCreateKbPanel = shallowRef(false);
const showUploadPanel = shallowRef(false);
const pipelineSearch = shallowRef("");
const ingestionTaskStatusFilter = shallowRef("all");
const keywordSearch = shallowRef("");
const userSearch = shallowRef("");
const editingDocumentId = shallowRef<number | null>(null);
const editingChunkId = shallowRef<number | null>(null);
const editDocumentTitle = shallowRef("");
const editDocumentEnabled = shallowRef(true);
const editChunkContent = shallowRef("");
const editChunkEnabled = shallowRef(true);
const inlineUploadFileInput = ref<HTMLInputElement | null>(null);
const documentPreviewLoading = shallowRef(false);
const documentPreview = shallowRef<KnowledgeDocumentPreviewResponse | null>(null);
const activeAdminModal = shallowRef<
  | "chunkEdit"
  | "documentPreview"
  | "intent"
  | "keyword"
  | "knowledgeBase"
  | "pipelineNodes"
  | "pipelineTask"
  | "uploadDocument"
  | "user"
  | null
>(null);

const knowledgeEmbeddingModelOptions = [
  { label: "SiliconFlow · Qwen/Qwen3-Embedding-8B", value: "Qwen/Qwen3-Embedding-8B" },
  { label: "LM Studio · Qwen/Qwen3-Embedding-8B-GGUF", value: "Qwen/Qwen3-Embedding-8B-GGUF" }
] as const;
const {
  editingKnowledgeBaseId,
  newKnowledgeBaseName,
  newKnowledgeEmbeddingModel,
  newKnowledgeCollectionName,
  resetKnowledgeBaseForm,
  fillKnowledgeBaseForm,
  buildKnowledgeBasePayload
} = useAdminKnowledgeBaseForm();
const {
  editingKeywordMappingId,
  newKeyword,
  newKeywordTarget,
  newKeywordMatchType,
  newKeywordPriority,
  newKeywordEnabled,
  newKeywordRemark,
  resetKeywordMappingForm,
  fillKeywordMappingForm,
  buildKeywordMappingPayload
} = useAdminKeywordMappingForm();
const {
  editingUserId,
  newAdminUsername,
  newAdminPassword,
  newAdminRole,
  newAdminAvatarUrl,
  resetUserForm,
  fillUserForm,
  buildUserCreatePayload,
  buildUserUpdatePayload
} = useAdminUserForm();
const {
  editingIntentNodeId,
  newIntentName,
  newIntentCode,
  newIntentLevel,
  newIntentType,
  newIntentParent,
  newIntentKnowledgeBaseId,
  newIntentMcpToolId,
  newIntentCollectionName,
  newIntentDescription,
  newIntentSampleQuestion,
  newIntentRuleSnippet,
  newIntentPrompt,
  newIntentParamPrompt,
  newIntentAdvanced,
  newIntentTopK,
  newIntentMinScore,
  newIntentSortOrder,
  newIntentEnabled,
  resetIntentNodeForm,
  fillIntentNodeForm,
  buildIntentNodePayload
} = useAdminIntentNodeForm();

const uploadAccept = ".txt,.md,.pdf,.doc,.docx,.xls,.xlsx,.html,.htm,text/plain,text/markdown,application/pdf";
const { pageSize: tablePageSize, pageSlice } = useAdminPagination(10);
const { toasts, pushToast, dismissToast } = useAdminToasts();
const {
  currentTab,
  knowledgeStage,
  sidebarCollapsed,
  pipelineTab,
  pipelineMenuOpen,
  navItems,
  navIconMap,
  pipelineNavItems,
  breadcrumbItems,
  activateTab,
  activatePipelineTab,
  toggleSidebar
} = useAdminNavigation({ selectedKnowledgeBaseId });
const knowledgeBasePage = shallowRef(1);
const documentPage = shallowRef(1);
const chunkPage = shallowRef(1);
const keywordPage = shallowRef(1);
const pipelinePage = shallowRef(1);
const ingestionTaskPage = shallowRef(1);
const userPage = shallowRef(1);

const { dashboardStats } = useAdminDashboardSummary(knowledgeBases);

const filteredKnowledgeBases = computed(() => {
  const query = knowledgeSearch.value.trim().toLowerCase();
  if (!query) {
    return knowledgeBases.value;
  }
  return knowledgeBases.value.filter((item) => {
    return item.name.toLowerCase().includes(query) || item.id.toLowerCase().includes(query);
  });
});

const pagedKnowledgeBases = computed(() => pageSlice(filteredKnowledgeBases.value, knowledgeBasePage.value));

const filteredDocuments = computed(() => {
  const query = documentSearch.value.trim().toLowerCase();
  return documents.value.filter((item) => {
    const matchesQuery =
      !query ||
      item.title.toLowerCase().includes(query) ||
      item.source_type.toLowerCase().includes(query) ||
      item.vector_index_status.toLowerCase().includes(query);
    const matchesStatus =
      documentStatusFilter.value === "all" || item.vector_index_status === documentStatusFilter.value;
    return matchesQuery && matchesStatus;
  });
});

const pagedDocuments = computed(() => pageSlice(filteredDocuments.value, documentPage.value));

const filteredChunks = computed(() => {
  if (chunkStatusFilter.value === "all") {
    return chunks.value;
  }
  if (chunkStatusFilter.value === "enabled") {
    return chunks.value.filter((item) => item.enabled);
  }
  return chunks.value.filter((item) => !item.enabled);
});

const pagedChunks = computed(() => pageSlice(filteredChunks.value, chunkPage.value));

const allVisibleChunksSelected = computed(() => {
  return pagedChunks.value.length > 0 && pagedChunks.value.every((item) => selectedChunkIds.value.includes(item.id));
});

const {
  editingPipelineId,
  newPipelineDescription,
  newPipelineName,
  pipelineEditorMode,
  pipelineJsonText,
  pipelineNodeDrafts,
  selectedPipelineName,
  selectedPipelineNodes,
  showPipelineModal,
  addPipelineNode,
  closeCreatePipelineModal,
  openCreatePipelineModal,
  openEditPipelineModal,
  openPipelineNodesModal: selectPipelineNodesForModal,
  removePipelineNode,
  syncPipelineFormFromJson,
  syncPipelineJsonFromForm,
  updatePipelineNodeConfigFromEvent
} = useAdminPipelineEditor();

const {
  newPipelineTaskPipelineId,
  newPipelineTaskSourceType,
  newPipelineTaskFile,
  newPipelineTaskMetadataText,
  clearPipelineTaskFile,
  onPipelineTaskFileSelected,
  pipelineTaskMetadataValid,
  resetPipelineTaskForm
} = useAdminPipelineTaskForm({ ingestionPipelines });

const pipelineRows = computed(() => {
  const query = pipelineSearch.value.trim().toLowerCase();
  return ingestionPipelines.value.map((pipeline) => ({
    id: pipeline.id,
    name: pipeline.name,
    description: pipeline.description || "-",
    nodeCount: pipeline.node_count,
    owner: pipeline.owner,
    updatedAt: pipeline.updated_at,
    taskCount: pipeline.name === "retriflow-ingestion-pipeline" ? ingestionTasks.value.length : 0,
    nodes: pipeline.nodes
  })).filter((pipeline) => {
    if (!query) {
      return true;
    }
    return `${pipeline.name} ${pipeline.description}`.toLowerCase().includes(query);
  });
});

const pagedPipelineRows = computed(() => pageSlice(pipelineRows.value, pipelinePage.value));
const filteredIngestionTasks = computed(() =>
  ingestionTasks.value.filter((task) => ingestionTaskStatusFilter.value === "all" || task.status === ingestionTaskStatusFilter.value)
);
const pagedIngestionTasks = computed(() => pageSlice(filteredIngestionTasks.value, ingestionTaskPage.value));

const {
  intentSearch,
  intentMode,
  selectedIntentNodeId,
  realIntentPage,
  realIntentRows,
  pagedRealIntentRows,
  selectedIntentNode,
  rootIntentNodes,
  childIntentNodes,
  intentNodeLevelClass,
  intentNodeTypeClass,
  selectIntentNode,
  selectFallbackIntentNode
} = useAdminIntentTree({ adminIntentNodes, knowledgeBases, pageSlice });

const realKeywordRows = computed(() => {
  const query = keywordSearch.value.trim().toLowerCase();
  return adminKeywordMappings.value
    .map((item) => {
      const kb = knowledgeBases.value.find((kbItem) => kbItem.id === item.knowledge_base_id);
      return {
        ...item,
        raw: item.raw_keyword,
        target: item.target_keyword,
        matchType: item.match_type,
        status: item.enabled ? "启用" : "停用",
        remark: item.remark || (kb ? `路由到 ${kb.name}` : "-"),
        updatedAt: item.updated_at
      };
    })
    .filter((item) => !query || item.raw.toLowerCase().includes(query) || item.target.toLowerCase().includes(query));
});

const pagedRealKeywordRows = computed(() => pageSlice(realKeywordRows.value, keywordPage.value));

const filteredTraces = computed(() => adminTraces.value);

const filteredAdminUsers = computed(() => {
  const query = userSearch.value.trim().toLowerCase();
  if (!query) {
    return adminUsers.value;
  }
  return adminUsers.value.filter((user) => user.username.toLowerCase().includes(query) || user.role.toLowerCase().includes(query));
});

const pagedAdminUsers = computed(() => pageSlice(filteredAdminUsers.value, userPage.value));

const traceRows = computed(() =>
  filteredTraces.value.map((trace) => ({
    name: "rag-stream-chat",
    id: trace.id,
    traceId: trace.trace_id || trace.id,
    owner: trace.owner_username || trace.owner_id || "unknown",
    messageCount: trace.message_count,
    latestMessageId: trace.latest_messages.at(-1)?.id ?? "-",
    duration: formatDuration(trace.duration_ms),
    status: trace.message_count > 0 ? "SUCCESS" : "EMPTY",
    executedAt: trace.latest_message_at,
    title: trace.title
  }))
);

const pagedTraceRows = computed(() => traceRows.value);

const selectedTraceRows = computed(() => {
  if (!selectedAdminTrace.value) {
    return [];
  }
  const totalDuration = Math.max(1, selectedAdminTrace.value.duration_ms);
  let elapsedDuration = 0;
  return selectedAdminTrace.value.messages.map((message) => {
    const durationMs = Math.max(0, message.duration_ms || 0);
    const offset = Math.min(88, Math.round((elapsedDuration / totalDuration) * 88));
    const width = durationMs > 0 ? Math.max(8, Math.min(92 - offset, Math.round((durationMs / totalDuration) * 88))) : 6;
    elapsedDuration += durationMs;
    return {
      id: message.id,
      name: message.role === "user" ? "user-message" : "assistant-response",
      type: message.role === "user" ? "USER_INPUT" : "LLM_OUTPUT",
      status: "SUCCESS",
      startedAt: message.created_at,
      duration: durationMs > 0 ? formatDuration(durationMs) : "0ms",
      offset,
      width,
      content: message.content_preview
    };
  });
});

const selectedTraceStats = computed(() => {
  const messages = selectedAdminTrace.value?.messages ?? [];
  const nodes = selectedAdminTraceNodes.value;
  const userMessages = messages.filter((message) => message.role === "user").length;
  const assistantMessages = messages.filter((message) => message.role === "assistant").length;
  return {
    nodeCount: nodes.length || Math.max(messages.length, 1),
    successCount: nodes.length ? nodes.filter((node) => node.status === "success").length : messages.length,
    failedCount: nodes.length ? nodes.filter((node) => node.status === "error").length : 0,
    userMessages,
    assistantMessages,
    totalDuration: formatDuration(selectedAdminTrace.value?.duration_ms ?? 0)
  };
});

watch([knowledgeSearch], () => {
  knowledgeBasePage.value = 1;
});

watch([documentSearch, documentStatusFilter, selectedKnowledgeBaseId], () => {
  documentPage.value = 1;
});

watch([chunkStatusFilter, selectedDocumentId], () => {
  chunkPage.value = 1;
});

watch([intentSearch], () => {
  realIntentPage.value = 1;
});

watch([keywordSearch], () => {
  keywordPage.value = 1;
});

watch([pipelineTab, pipelineSearch, ingestionTaskStatusFilter], () => {
  pipelinePage.value = 1;
  ingestionTaskPage.value = 1;
});

watch(adminTraceId, () => {
  adminTraceId.value = adminTraceId.value.replace(/\D/gu, "").slice(0, 20);
});

watch([userSearch], () => {
  userPage.value = 1;
});

watch(infoMessage, (message) => {
  if (!message) {
    return;
  }
  pushToast(message, "success");
  infoMessage.value = "";
});

function handleAdminGlobalKeydown(event: KeyboardEvent) {
  if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "k") {
    return;
  }
  event.preventDefault();
  activateTab("knowledge");
  void nextTick(() => {
    adminSearchInput.value?.focus();
    adminSearchInput.value?.select();
  });
}

onMounted(() => {
  window.addEventListener("keydown", handleAdminGlobalKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleAdminGlobalKeydown);
});

function settingValue(key: string, fallback = "-") {
  return adminSettings.value.find((item) => item.key === key)?.value || fallback;
}

const settingCards = computed<SettingCard[]>(() => [
  {
    title: "RAG 默认配置",
    items: [
      { label: "Collection", value: settingValue("pgvector_table") },
      { label: "Vector Store", value: settingValue("vector_store_type") },
      { label: "Database", value: `${settingValue("database_backend")} / ${settingValue("database_schema")}` },
      { label: "TopK", value: `BM25 ${settingValue("retrieval_bm25_top_k")} · Vector ${settingValue("retrieval_vector_top_k")} · Final ${settingValue("retrieval_final_top_k")}` }
    ]
  },
  {
    title: "查询改写",
    items: [
      { label: "Provider", value: settingValue("rewrite_provider") },
      { label: "Mode", value: "会话记忆后、检索前执行" }
    ]
  },
  {
    title: "记忆管理",
    items: [
      { label: "短期记忆", value: "摘要 + 最近 N 轮" },
      { label: "中长期记忆", value: "当前第一版存储与召回能力" }
    ]
  },
  {
    title: "模型服务提供方",
    items: [
      { label: "Chat Provider", value: settingValue("chat_provider") },
      { label: "Route Provider", value: settingValue("route_provider") },
      { label: "Intent Provider", value: settingValue("intent_provider") },
      { label: "Embedding Provider", value: settingValue("embedding_provider") },
      { label: "Rerank Provider", value: settingValue("rerank_provider") },
      { label: "LM Studio", value: settingValue("lmstudio_base_url") }
    ]
  },
  {
    title: "模型选择策略",
    items: [
      { label: "Chat Model", value: settingValue("default_chat_model") },
      { label: "Deep Thinking", value: settingValue("deep_thinking_model") },
      { label: "Embedding Model", value: settingValue("default_embedding_model") },
      { label: "LM Chat", value: settingValue("lmstudio_chat_model") },
      { label: "LM Embedding", value: settingValue("lmstudio_embedding_model") },
      { label: "Rerank Model", value: settingValue("default_rerank_model") }
    ]
  },
  {
    title: "流式响应",
    items: [
      { label: "Chat Endpoint", value: "/api/v1/chat/stream" },
      { label: "Render Mode", value: "SSE delta 流式输出" }
    ]
  },
  {
    title: "检索治理",
    items: [
      { label: "跨请求缓存", value: settingValue("retrieval_cross_request_cache_enabled") },
      { label: "缓存 TTL", value: `${settingValue("retrieval_cross_request_cache_ttl_seconds")} 秒` },
      { label: "缓存容量", value: settingValue("retrieval_cross_request_cache_max_entries") }
    ]
  },
  {
    title: "本地服务",
    items: [
      { label: "Tika Enabled", value: settingValue("tika_enabled") },
      { label: "Tika Endpoint", value: settingValue("tika_endpoint") },
      { label: "OCR Enabled", value: settingValue("tika_ocr_enabled") },
      { label: "OCR Endpoint", value: settingValue("tika_ocr_service_endpoint") }
    ]
  },
  {
    title: "链路追踪",
    items: [
      { label: "LangSmith", value: settingValue("langsmith_tracing") },
      { label: "Project", value: settingValue("langsmith_project") }
    ]
  }
]);

function closeAdminModal() {
  activeAdminModal.value = null;
}

function clearAdminError() {
  error.value = "";
}

function openKnowledgeBaseModal() {
  resetKnowledgeBaseForm();
  activeAdminModal.value = "knowledgeBase";
}

function openKnowledgeBaseEditModal(knowledgeBaseId: string) {
  const knowledgeBase = knowledgeBases.value.find((item) => item.id === knowledgeBaseId);
  if (!knowledgeBase) {
    return;
  }
  fillKnowledgeBaseForm(knowledgeBase);
  activeAdminModal.value = "knowledgeBase";
}

function openUploadDocumentModal() {
  editingDocumentId.value = null;
  editDocumentTitle.value = "";
  editDocumentEnabled.value = true;
  uploadProcessMode.value = "chunk_strategy";
  uploadPipelineId.value = ingestionPipelines.value[0]?.id ?? null;
  uploadChunkStrategy.value = "structure_aware";
  uploadChunkSize.value = 1400;
  uploadChunkOverlap.value = 0;
  uploadStructureMaxChars.value = 1800;
  uploadStructureMinChars.value = 600;
  selectedUploadFile.value = null;
  selectedUploadFileName.value = "";
  activeAdminModal.value = "uploadDocument";
}

function openPipelineTaskModal() {
  resetPipelineTaskForm();
  activeAdminModal.value = "pipelineTask";
}

async function createPipelineTaskFromModal() {
  if (newPipelineTaskSourceType.value !== "local_file" || !newPipelineTaskFile.value || !newPipelineTaskPipelineId.value) {
    return;
  }
  if (!pipelineTaskMetadataValid()) {
    error.value = "任务元数据不是合法 JSON。";
    return;
  }
  if (!selectedKnowledgeBaseId.value && knowledgeBases.value[0]) {
    selectKnowledgeBase(knowledgeBases.value[0].id);
  }
  if (!selectedKnowledgeBaseId.value) {
    error.value = "请先创建知识库后再新建通道任务。";
    return;
  }
  uploadProcessMode.value = "data_channel";
  uploadPipelineId.value = newPipelineTaskPipelineId.value;
  const created = await uploadDocument(newPipelineTaskFile.value);
  if (!created) {
    return;
  }
  clearPipelineTaskFile();
  closeAdminModal();
  await refreshKnowledgeData();
  pipelineTab.value = "tasks";
}

function openDocumentEditModal(documentId: number) {
  const document = documents.value.find((item) => item.id === documentId);
  if (!document) {
    return;
  }
  const config = document.processing_config ?? {};
  const chunkConfig = config.chunkConfig ?? {};
  editingDocumentId.value = document.id;
  editDocumentTitle.value = document.title;
  editDocumentEnabled.value = document.enabled;
  uploadProcessMode.value = config.processMode === "data_channel" || document.processing_mode === "data_channel" ? "data_channel" : "chunk_strategy";
  uploadPipelineId.value =
    typeof config.pipelineId === "number"
      ? config.pipelineId
      : ingestionPipelines.value[0]?.id ?? null;
  uploadChunkStrategy.value = config.chunkStrategy ?? "structure_aware";
  uploadChunkSize.value =
    typeof config.chunkSize === "number"
      ? config.chunkSize
      : typeof chunkConfig.targetChars === "number"
        ? chunkConfig.targetChars
        : 1400;
  uploadChunkOverlap.value =
    typeof config.chunkOverlap === "number"
      ? config.chunkOverlap
      : typeof chunkConfig.overlapChars === "number"
        ? chunkConfig.overlapChars
        : 0;
  uploadStructureMaxChars.value = typeof chunkConfig.maxChars === "number" ? chunkConfig.maxChars : 1800;
  uploadStructureMinChars.value = typeof chunkConfig.minChars === "number" ? chunkConfig.minChars : 600;
  uploadRecursiveSeparatorsText.value =
    serializeUploadRecursiveSeparators(config.recursiveSeparators) ?? uploadRecursiveSeparatorsText.value;
  selectedUploadFile.value = null;
  selectedUploadFileName.value = document.source_uri || document.title;
  activeAdminModal.value = "uploadDocument";
}

function openChunkEditModal(chunkId: number) {
  const chunk = chunks.value.find((item) => item.id === chunkId);
  if (!chunk) {
    return;
  }
  editingChunkId.value = chunk.id;
  editChunkContent.value = chunk.content;
  editChunkEnabled.value = chunk.enabled;
  activeAdminModal.value = "chunkEdit";
}

async function openDocumentPreview(documentId: number) {
  documentPreviewLoading.value = true;
  documentPreview.value = null;
  activeAdminModal.value = "documentPreview";
  try {
    documentPreview.value = await fetchKnowledgeDocumentPreview(selectedKnowledgeBaseId.value, documentId);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "文档预览失败";
    closeAdminModal();
  } finally {
    documentPreviewLoading.value = false;
  }
}

async function openDocumentSource(documentId: number) {
  try {
    const { blob, filename } = await downloadKnowledgeDocumentSource(selectedKnowledgeBaseId.value, documentId);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "源文件下载失败";
  }
}

function openKeywordModal() {
  resetKeywordMappingForm();
  activeAdminModal.value = "keyword";
}

function openKeywordEditModal(mappingId: string) {
  const mapping = adminKeywordMappings.value.find((item) => item.id === mappingId);
  if (!mapping) {
    return;
  }
  fillKeywordMappingForm(mapping);
  activeAdminModal.value = "keyword";
}

function openUserModal() {
  resetUserForm();
  activeAdminModal.value = "user";
}

function openUserEditModal(userId: string) {
  const user = adminUsers.value.find((item) => item.id === userId);
  if (!user) {
    return;
  }
  fillUserForm(user);
  activeAdminModal.value = "user";
}

function openIntentModal() {
  resetIntentNodeForm({
    knowledgeBaseId: selectedKnowledgeBaseId.value,
    collectionName: selectedKnowledgeBase.value?.collection_name || ""
  });
  activeAdminModal.value = "intent";
}

function openIntentChildModal(parentId: string) {
  openIntentModal();
  newIntentParent.value = parentId;
}

function openIntentEditModal(nodeId: string) {
  const node = adminIntentNodes.value.find((item) => item.id === nodeId);
  if (!node) {
    return;
  }
  selectIntentNode(node.id);
  fillIntentNodeForm(node);
  activeAdminModal.value = "intent";
}

async function deleteIntentNodeFromInput(nodeId: string) {
  await removeIntentNode(nodeId);
  if (selectedIntentNodeId.value === nodeId) {
    selectFallbackIntentNode();
  }
}

async function addKeywordFromInput() {
  if (!newKeyword.value.trim()) {
    return;
  }
  const payload = buildKeywordMappingPayload(selectedKnowledgeBaseId.value);
  if (editingKeywordMappingId.value) {
    await updateKeywordMapping(editingKeywordMappingId.value, payload);
  } else {
    await createKeywordMapping(payload);
  }
  resetKeywordMappingForm();
  closeAdminModal();
}

function selectedUploadFileLabel() {
  if (editingDocumentId.value) {
    return selectedUploadFileName.value || "保留原文件";
  }
  return selectedUploadFile.value?.name || "未选择文件";
}

function onUploadFileSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0] ?? null;
  selectedUploadFile.value = file;
  selectedUploadFileName.value = file?.name ?? "";
}

function removeKeywordByValue(keyword: string) {
  const mapping = adminKeywordMappings.value.find((item) => item.raw_keyword === keyword || item.id === keyword);
  if (mapping) {
    void removeKeywordMapping(mapping.id);
  }
}

async function createAdminUserFromInput() {
  if (editingUserId.value) {
    if (!newAdminUsername.value.trim()) {
      return;
    }
    await saveUser(editingUserId.value, buildUserUpdatePayload());
    closeAdminModal();
    return;
  }
  if (!newAdminUsername.value.trim() || !newAdminPassword.value.trim()) {
    return;
  }
  await createUser(buildUserCreatePayload());
  resetUserForm();
  closeAdminModal();
}

async function createKnowledgeBaseFromInput() {
  if (!newKnowledgeBaseName.value.trim()) {
    return;
  }
  if (editingKnowledgeBaseId.value) {
    const updated = await saveKnowledgeBase(editingKnowledgeBaseId.value, buildKnowledgeBasePayload());
    if (updated) {
      closeAdminModal();
    }
    return;
  }
  await addKnowledgeBase(buildKnowledgeBasePayload());
  resetKnowledgeBaseForm();
  knowledgeStage.value = "knowledge-bases";
  closeAdminModal();
}

async function saveDocumentEditFromModal() {
  if (editingDocumentId.value === null || !editDocumentTitle.value.trim()) {
    return;
  }
  const updated = await saveDocument(editingDocumentId.value, {
    title: editDocumentTitle.value.trim(),
    enabled: editDocumentEnabled.value,
    documentType: "knowledge_base",
    processMode: uploadProcessMode.value,
    pipelineId: uploadProcessMode.value === "data_channel" ? uploadPipelineId.value ?? undefined : undefined,
    chunkStrategy: uploadChunkStrategy.value,
    chunkSize: uploadChunkSize.value,
    chunkOverlap: uploadChunkOverlap.value,
    recursiveSeparators: parseUploadRecursiveSeparators(uploadRecursiveSeparatorsText.value),
    chunkConfig: buildUploadChunkConfig({
      chunkOverlap: uploadChunkOverlap.value,
      chunkSize: uploadChunkSize.value,
      chunkStrategy: uploadChunkStrategy.value,
      recursiveSeparatorsText: uploadRecursiveSeparatorsText.value,
      structureMaxChars: uploadStructureMaxChars.value,
      structureMinChars: uploadStructureMinChars.value
    })
  });
  if (updated) {
    closeAdminModal();
  }
}

async function saveChunkEditFromModal() {
  if (editingChunkId.value === null || !editChunkContent.value.trim()) {
    return;
  }
  const updated = await saveChunk(editingChunkId.value, {
    content: editChunkContent.value,
    enabled: editChunkEnabled.value
  });
  if (updated) {
    closeAdminModal();
  }
}

async function openDocuments(knowledgeBaseId: string) {
  selectKnowledgeBase(knowledgeBaseId);
  await loadDocuments(knowledgeBaseId);
  knowledgeStage.value = "documents";
}

function backToKnowledgeBases() {
  selectKnowledgeBase("");
  knowledgeStage.value = "knowledge-bases";
  closeAdminModal();
}

async function openChunks(documentId: number) {
  selectDocument(documentId);
  await loadChunks(selectedKnowledgeBaseId.value, documentId);
  selectedChunkIds.value = [];
  knowledgeStage.value = "chunks";
}

function backToDocuments() {
  knowledgeStage.value = "documents";
}

async function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0] ?? null;
  selectedUploadFileName.value = file?.name ?? "";
  const created = await uploadDocument(file);
  input.value = "";
  if (created) {
    closeAdminModal();
    await refreshKnowledgeData();
  }
}

async function uploadSelectedDocumentFromModal() {
  if (editingDocumentId.value !== null) {
    await saveDocumentEditFromModal();
    return;
  }
  if (!selectedUploadFile.value) {
    return;
  }
  const created = await uploadDocument(selectedUploadFile.value);
  if (!created) {
    return;
  }
  selectedUploadFile.value = null;
  closeAdminModal();
  await refreshKnowledgeData();
}

async function createIntentFromInput() {
  if (!newIntentName.value.trim()) {
    return;
  }
  const payload = buildIntentNodePayload();
  const saved = editingIntentNodeId.value
    ? await updateIntentNode(editingIntentNodeId.value, payload)
    : await createIntentNode(payload);
  if (saved) {
    selectIntentNode(saved.id);
    intentMode.value = "tree";
    closeAdminModal();
  } else {
    closeAdminModal();
  }
}

async function runChunking(documentId: number) {
  selectDocument(documentId);
  await reindexDocument();
  selectedChunkIds.value = [];
  await refreshKnowledgeData(documentId);
}

function toggleVisibleChunkSelection() {
  if (allVisibleChunksSelected.value) {
    const visibleIds = new Set(filteredChunks.value.map((item) => item.id));
    selectedChunkIds.value = selectedChunkIds.value.filter((id) => !visibleIds.has(id));
    return;
  }

  selectedChunkIds.value = Array.from(new Set([...selectedChunkIds.value, ...filteredChunks.value.map((item) => item.id)]));
}

async function setChunkEnabled(chunkId: number, enabled: boolean) {
  if (!selectedDocumentId.value) {
    return;
  }
  await updateKnowledgeChunk(selectedKnowledgeBaseId.value, selectedDocumentId.value, chunkId, enabled);
  await loadChunks(selectedKnowledgeBaseId.value, selectedDocumentId.value);
}

async function setSelectedChunksEnabled(enabled: boolean) {
  if (!selectedDocumentId.value) {
    return;
  }
  await updateKnowledgeChunks(selectedKnowledgeBaseId.value, selectedDocumentId.value, selectedChunkIds.value, enabled);
  selectedChunkIds.value = [];
  await loadChunks(selectedKnowledgeBaseId.value, selectedDocumentId.value);
}

async function setAllChunksEnabled(enabled: boolean) {
  if (!selectedDocumentId.value) {
    return;
  }
  await updateKnowledgeChunks(selectedKnowledgeBaseId.value, selectedDocumentId.value, [], enabled);
  selectedChunkIds.value = [];
  await loadChunks(selectedKnowledgeBaseId.value, selectedDocumentId.value);
}

async function removeChunk(chunkId: number) {
  if (!selectedDocumentId.value) {
    return;
  }
  await deleteKnowledgeChunk(selectedKnowledgeBaseId.value, selectedDocumentId.value, chunkId);
  selectedChunkIds.value = selectedChunkIds.value.filter((id) => id !== chunkId);
  await refreshKnowledgeData(selectedDocumentId.value);
  await loadChunks(selectedKnowledgeBaseId.value, selectedDocumentId.value);
}

function openPipelineNodesModal(pipeline: { name: string; nodes: IngestionPipelineNodeConfig[] }) {
  selectPipelineNodesForModal(pipeline);
  activeAdminModal.value = "pipelineNodes";
}

async function savePipelineFromModal() {
  if (!newPipelineName.value.trim()) {
    return;
  }

  let nodes = pipelineNodeDrafts.value;
  if (pipelineEditorMode.value === "json") {
    try {
      const parsed = JSON.parse(pipelineJsonText.value) as IngestionPipelineNodeConfig[];
      if (!Array.isArray(parsed)) {
        return;
      }
      nodes = parsed.map((node, index) => ({
        node_id: String(node.node_id || `node-${index + 1}`),
        node_type: String(node.node_type || "custom"),
        next_node_id: String(node.next_node_id || ""),
        condition: String(node.condition || ""),
        config: typeof node.config === "object" && node.config !== null && !Array.isArray(node.config) ? node.config : {}
      }));
    } catch {
      return;
    }
  }

  const payload = {
    name: newPipelineName.value.trim(),
    description: newPipelineDescription.value.trim(),
    owner: "admin",
    nodes
  };
  if (editingPipelineId.value !== null) {
    await updatePipeline(editingPipelineId.value, payload);
  } else {
    await createPipeline(payload);
  }
  closeCreatePipelineModal();
}

async function deletePipelineFromRow(pipelineId: number) {
  if (!window.confirm("确认删除这条流水线吗？")) {
    return;
  }
  await removePipeline(pipelineId);
}

</script>

<template>
  <div class="admin-layout" :class="{ collapsed: sidebarCollapsed }">
    <AdminToastStack :toasts="toasts" @dismiss="dismissToast" />

    <aside class="admin-sidebar">
      <div class="admin-brand">
        <div class="brand-icon">R</div>
        <div class="brand-copy">
          <h2>RetriFlow 管理后台</h2>
          <span>Knowledge Console</span>
        </div>
      </div>

      <div class="nav-section-title">导航</div>
      <template
        v-for="item in navItems.filter((nav) => nav.group === 'main')"
        :key="item.key"
      >
      <button
        class="nav-item"
        :class="{ active: currentTab === item.key || (item.key === 'pipeline' && pipelineMenuOpen) }"
        type="button"
        @click="activateTab(item.key)"
      >
        <span class="nav-icon" aria-hidden="true">{{ navIconMap[item.key] }}</span>
        <span class="nav-label">{{ item.label }}</span>
        <span v-if="item.key === 'pipeline'" class="nav-chevron" aria-hidden="true">{{ pipelineMenuOpen ? "⌄" : "›" }}</span>
      </button>
        <div v-if="item.key === 'pipeline' && pipelineMenuOpen" class="nav-sub-items">
          <button
            v-for="pipelineItem in pipelineNavItems"
            :key="pipelineItem.key"
            class="nav-sub-item"
            :class="{ active: currentTab === 'pipeline' && pipelineTab === pipelineItem.key }"
            type="button"
            @click="activatePipelineTab(pipelineItem.key)"
          >
            <span class="nav-icon" aria-hidden="true">{{ pipelineItem.icon }}</span>
            <span>{{ pipelineItem.label }}</span>
          </button>
        </div>
      </template>

      <div class="nav-section-title settings-title">设置</div>
      <button
        v-for="item in navItems.filter((nav) => nav.group === 'settings')"
        :key="item.key"
        class="nav-item"
        :class="{ active: currentTab === item.key }"
        type="button"
        @click="activateTab(item.key)"
      >
        <span class="nav-icon" aria-hidden="true">{{ navIconMap[item.key] }}</span>
        <span class="nav-label">{{ item.label }}</span>
      </button>

      <button class="collapse-btn" type="button" @click="toggleSidebar">
        {{ sidebarCollapsed ? "展开" : "收起侧边栏" }}
      </button>
    </aside>

    <main class="admin-main">
      <header class="admin-header">
        <div class="search-box">
          <span>⌕</span>
          <input
            ref="adminSearchInput"
            v-model="knowledgeSearch"
            type="text"
            placeholder="筛选知识库..."
            @focus="activateTab('knowledge')"
          />
          <kbd>Ctrl K</kbd>
        </div>
        <div class="header-actions">
          <button class="ghost-btn" type="button" @click="router.push('/chat')">返回聊天</button>
          <div class="user-pill">
            <span class="avatar">{{ authStore.currentUser?.username?.slice(0, 1).toUpperCase() || "A" }}</span>
            <span>{{ authStore.currentUser?.username || "admin" }}</span>
          </div>
        </div>
      </header>

      <section class="admin-content">
        <div class="breadcrumb">{{ breadcrumbItems.join(" / ") }}</div>

        <AdminNotice v-if="readonlyNotice" :message="readonlyNotice" />
        <AdminNotice v-if="error" tone="danger" :message="error" dismissible @dismiss="clearAdminError" />

        <template v-if="currentTab === 'knowledge'">
          <div v-if="knowledgeStage === 'knowledge-bases'" class="page-head">
            <div>
              <h1>知识库管理</h1>
              <p>先创建知识库，再进入文档管理上传与切块。</p>
            </div>
            <div class="page-actions">
              <input v-model="knowledgeSearch" class="ui-input" type="text" placeholder="搜索知识库名称" />
                  <button class="ghost-btn" type="button" @click="void refreshKnowledgeData()">刷新</button>
              <button
                v-if="canManageKnowledge"
                class="primary-btn"
                type="button"
                @click="openKnowledgeBaseModal"
              >
                + 新建知识库
              </button>
            </div>
          </div>

          <div v-if="knowledgeStage === 'knowledge-bases'" class="metric-grid">
            <article class="metric-card">
              <span>知识库</span>
              <strong>{{ dashboardStats.knowledgeBaseCount }}</strong>
            </article>
            <article class="metric-card">
              <span>文档数</span>
              <strong>{{ dashboardStats.documentCount }}</strong>
            </article>
            <article class="metric-card">
              <span>已切块文档</span>
              <strong>{{ dashboardStats.indexedDocumentCount }}</strong>
            </article>
            <article class="metric-card">
              <span>分块数</span>
              <strong>{{ dashboardStats.chunkCount }}</strong>
            </article>
          </div>

          <section v-if="knowledgeStage === 'knowledge-bases' && showCreateKbPanel" class="form-panel">
            <label>
              知识库名称
              <input v-model="newKnowledgeBaseName" class="ui-input" type="text" placeholder="例如：人事制度" />
            </label>
            <button class="primary-btn" type="button" @click="createKnowledgeBaseFromInput">确认创建</button>
          </section>

          <AdminKnowledgeBaseTable
            v-if="knowledgeStage === 'knowledge-bases'"
            :can-manage-knowledge="canManageKnowledge"
            :items="pagedKnowledgeBases"
            :loading="loading"
            :page="knowledgeBasePage"
            :page-size="tablePageSize"
            :total="filteredKnowledgeBases.length"
            @delete="removeKnowledgeBase"
            @edit="openKnowledgeBaseEditModal"
            @open-documents="openDocuments"
            @page-change="knowledgeBasePage = $event"
          />

          <template v-if="knowledgeStage === 'documents'">
            <div class="page-head">
              <div>
                <h1>文档管理</h1>
                <p>{{ selectedKnowledgeBase?.name }}（{{ selectedKnowledgeBase?.collection_name || selectedKnowledgeBase?.id }}）</p>
              </div>
              <div class="page-actions">
                <button class="ghost-btn" type="button" @click="backToKnowledgeBases">返回知识库</button>
                <button
                  v-if="canManageKnowledge"
                  class="primary-btn"
                  type="button"
                  @click="openUploadDocumentModal"
                >
                  上传文档
                </button>
              </div>
            </div>

            <section v-if="showUploadPanel" class="form-panel upload-panel">
              <p class="form-hint wide">上传后会解析文档内容用于预览；下方配置会保存到文档，后续点击“切块”时直接按这些参数执行。</p>
              <label class="wide">
                处理模式
                <select v-model="uploadProcessMode">
                  <option value="chunk_strategy">按切块策略处理</option>
                  <option value="data_channel">按数据通道处理</option>
                </select>
              </label>
              <label v-if="uploadProcessMode === 'chunk_strategy'" class="wide">
                切块策略
                <select v-model="uploadChunkStrategy">
                  <option v-for="option in chunkStrategyOptions" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
              </label>
              <label v-else class="wide">
                数据通道
                <select v-model.number="uploadPipelineId" :disabled="ingestionPipelines.length === 0">
                  <option v-if="ingestionPipelines.length === 0" :value="null">暂无数据通道</option>
                  <option v-for="pipeline in ingestionPipelines" :key="pipeline.id" :value="pipeline.id">
                    {{ pipeline.name }}
                  </option>
                </select>
              </label>
              <template v-if="uploadProcessMode === 'chunk_strategy'">
                <template v-if="uploadChunkStrategy === 'structure_aware'">
                  <div class="form-row">
                    <label>
                      理想块大小
                      <input v-model.number="uploadChunkSize" min="1" type="number" />
                    </label>
                    <label>
                      块上限
                      <input v-model.number="uploadStructureMaxChars" min="1" type="number" />
                    </label>
                  </div>
                  <div class="form-row">
                    <label>
                      块下限
                      <input v-model.number="uploadStructureMinChars" min="1" type="number" />
                    </label>
                    <label>
                      重叠大小
                      <input v-model.number="uploadChunkOverlap" min="0" type="number" />
                    </label>
                  </div>
                </template>
                <div v-else-if="uploadShowChunkSizeControls" class="form-row">
                  <label>
                    Chunk Size
                    <input v-model.number="uploadChunkSize" min="1" type="number" />
                  </label>
                  <label>
                    Overlap
                    <input v-model.number="uploadChunkOverlap" min="0" type="number" />
                  </label>
                </div>
                <label v-if="uploadShowRecursiveSeparatorControls" class="wide">
                  递归分隔符
                  <textarea v-model="uploadRecursiveSeparatorsText" rows="4"></textarea>
                </label>
                <p class="form-hint wide">{{ uploadChunkSummary }}</p>
                <p v-if="uploadAutoStrategyRecommendation" class="form-hint wide">{{ uploadAutoStrategyRecommendation }}</p>
                <p v-if="uploadShowRecursiveSeparatorControls" class="form-hint wide">{{ uploadRecursiveSeparatorSummary }}</p>
                <p v-if="uploadShowSemanticNotice" class="form-hint wide">语义切块会保留策略配置，后端按当前可用能力执行。</p>
              </template>
              <input ref="inlineUploadFileInput" :accept="uploadAccept" hidden type="file" @change="onFileChange" />
              <button class="primary-btn wide" type="button" :disabled="uploadLoading" @click="inlineUploadFileInput?.click()">
                {{ uploadLoading ? "上传并解析中..." : "选择文件并上传" }}
              </button>
              <p v-if="selectedUploadFileName" class="form-hint wide">最近选择：{{ selectedUploadFileName }}</p>
            </section>

            <AdminDocumentTable
              :can-manage-knowledge="canManageKnowledge"
              :document-loading="documentLoading"
              :document-type-label="documentTypeLabel"
              :items="pagedDocuments"
              :page="documentPage"
              :page-size="tablePageSize"
              :processing-mode-label="processingModeLabel"
              :reindexing-document-id="reindexingDocumentId"
              :source-label="sourceLabel"
              :status-class="statusClass"
              :status-label="statusLabel"
              :total="filteredDocuments.length"
              @delete="removeDocument"
              @edit="openDocumentEditModal"
              @open-chunks="openChunks"
              @page-change="documentPage = $event"
              @preview="openDocumentPreview"
              @reindex="runChunking"
            >
              <template #toolbar>
                <div class="toolbar-actions">
                  <input v-model="documentSearch" class="ui-input" type="text" placeholder="搜索文档名称" />
                  <select v-model="documentStatusFilter" class="ui-input">
                    <option value="all">全部状态</option>
                    <option value="indexed">切块成功</option>
                    <option value="pending">待切块</option>
                    <option value="failed">切块失败</option>
                  </select>
                  <button class="ghost-btn" type="button" @click="loadDocuments(selectedKnowledgeBaseId)">刷新</button>
                </div>
              </template>
            </AdminDocumentTable>
          </template>

          <template v-if="knowledgeStage === 'chunks'">
            <div class="page-head">
              <div>
                <h1>分块管理</h1>
                <p>{{ selectedDocument?.title }}（知识库：{{ selectedKnowledgeBase?.name }}）</p>
              </div>
              <div class="page-actions">
                <button class="ghost-btn" type="button" @click="backToDocuments">返回文档</button>
                <button
                  v-if="canManageKnowledge"
                  class="primary-btn"
                  type="button"
                  :disabled="reindexLoading"
                  @click="selectedDocumentId && runChunking(selectedDocumentId)"
                >
                  重新向量
                </button>
              </div>
            </div>

            <AdminChunkTable
              v-model:selected-chunk-ids="selectedChunkIds"
              :all-visible-selected="allVisibleChunksSelected"
              :chunk-loading="chunkLoading"
              :chunk-metadata-summary="chunkMetadataSummary"
              :items="pagedChunks"
              :page="chunkPage"
              :page-size="tablePageSize"
              :total="filteredChunks.length"
              @delete="removeChunk"
              @edit="openChunkEditModal"
              @page-change="chunkPage = $event"
              @toggle-visible-selection="toggleVisibleChunkSelection"
              @update-enabled="setChunkEnabled"
            >
              <template #toolbar>
                <div class="toolbar-actions">
                  <select v-model="chunkStatusFilter" class="ui-input">
                    <option value="all">全部状态</option>
                    <option value="enabled">启用</option>
                    <option value="disabled">禁用</option>
                  </select>
                  <button
                    class="ghost-btn"
                    type="button"
                    :disabled="selectedChunkIds.length === 0"
                    @click="setSelectedChunksEnabled(true)"
                  >
                    批量启用
                  </button>
                  <button
                    class="ghost-btn"
                    type="button"
                    :disabled="selectedChunkIds.length === 0"
                    @click="setSelectedChunksEnabled(false)"
                  >
                    批量禁用
                  </button>
                  <button class="ghost-btn" type="button" @click="setAllChunksEnabled(true)">全量启用</button>
                  <button class="ghost-btn" type="button" @click="setAllChunksEnabled(false)">全量禁用</button>
                  <button
                    class="ghost-btn"
                    type="button"
                    @click="selectedDocumentId && loadChunks(selectedKnowledgeBaseId, selectedDocumentId)"
                  >
                    刷新
                  </button>
                </div>
              </template>
            </AdminChunkTable>
          </template>
        </template>

        <template v-else-if="currentTab === 'dashboard'">
          <AdminDashboardPanel
            :dashboard="adminDashboard"
            :dashboard-range="dashboardRange"
            @change-range="(value) => void loadDashboard(value)"
            @refresh="() => void loadDashboard(dashboardRange)"
          />
        </template>

        <template v-else-if="currentTab === 'intent'">
          <AdminIntentPanel
            v-model:intent-mode="intentMode"
            v-model:intent-search="intentSearch"
            v-model:real-intent-page="realIntentPage"
            v-model:selected-intent-node-id="selectedIntentNodeId"
            :admin-intent-node-count="adminIntentNodes.length"
            :child-intent-nodes="childIntentNodes"
            :intent-node-level-class="intentNodeLevelClass"
            :intent-node-type-class="intentNodeTypeClass"
            :paged-real-intent-rows="pagedRealIntentRows"
            :real-intent-rows-total="realIntentRows.length"
            :root-intent-nodes="rootIntentNodes"
            :selected-intent-node="selectedIntentNode"
            :table-page-size="tablePageSize"
            @create="openIntentModal"
            @create-child="openIntentChildModal"
            @delete="deleteIntentNodeFromInput"
            @edit="openIntentEditModal"
            @refresh="refreshKnowledgeData"
          />
        </template>
        <template v-else-if="currentTab === 'keyword'">
          <AdminKeywordMappingsPanel
            v-model:keyword-page="keywordPage"
            v-model:keyword-search="keywordSearch"
            :can-save="!routeProfileLoading && Boolean(routeProfile)"
            :page-size="tablePageSize"
            :rows="pagedRealKeywordRows"
            :total="realKeywordRows.length"
            @create="openKeywordModal"
            @delete="removeKeywordByValue"
            @edit="openKeywordEditModal"
            @save="saveRouteProfile"
          />
        </template>

        <template v-else-if="currentTab === 'pipeline'">
          <div class="page-head">
            <div>
              <h1>数据通道</h1>
              <p>{{ pipelineTab === "pipelines" ? "配置节点顺序与处理逻辑。" : "监控流水线任务执行状态。" }}</p>
            </div>
          </div>

          <AdminPipelineTables
            :active-tab="pipelineTab"
            :page-size="tablePageSize"
            :pipeline-page="pipelinePage"
            :pipeline-rows="pagedPipelineRows"
            :pipeline-total="pipelineRows.length"
            :source-label="sourceLabel"
            :task-page="ingestionTaskPage"
            :task-total="filteredIngestionTasks.length"
            :tasks="pagedIngestionTasks"
            @delete-pipeline="deletePipelineFromRow"
            @edit-pipeline="openEditPipelineModal"
            @page-pipeline="pipelinePage = $event"
            @page-task="ingestionTaskPage = $event"
            @view-pipeline-nodes="openPipelineNodesModal"
          >
            <template #pipeline-toolbar>
              <div class="toolbar-actions">
                <input v-model="pipelineSearch" class="ui-input toolbar-input" type="text" placeholder="搜索流水线名称" />
                <button class="ghost-btn" type="button" @click="pipelinePage = 1">搜索</button>
                <button class="ghost-btn" type="button" @click="void refreshKnowledgeData()">刷新</button>
                <button class="primary-btn" type="button" @click="openCreatePipelineModal">新建流水线</button>
              </div>
            </template>
            <template #task-toolbar>
                <div class="toolbar-actions">
                  <select v-model="ingestionTaskStatusFilter" class="ui-input toolbar-select">
                    <option value="all">全部状态</option>
                    <option value="pending">pending</option>
                    <option value="running">running</option>
                    <option value="completed">completed</option>
                    <option value="failed">failed</option>
                  </select>
                  <button class="ghost-btn" type="button" @click="void refreshKnowledgeData()">刷新</button>
                  <button class="ghost-btn" type="button" @click="openPipelineTaskModal">上传文件</button>
                  <button class="primary-btn" type="button" @click="openPipelineTaskModal">新建任务</button>
                </div>
            </template>
          </AdminPipelineTables>
        </template>

        <template v-else-if="currentTab === 'trace'">
          <AdminTracePanel
            v-model:trace-id="adminTraceId"
            :admin-trace-page="adminTracePage"
            :admin-trace-page-size="adminTracePageSize"
            :admin-trace-total="adminTraceTotal"
            :rows="pagedTraceRows"
            :selected-admin-trace="selectedAdminTrace"
            :selected-admin-trace-nodes="selectedAdminTraceNodes"
            :selected-trace-rows="selectedTraceRows"
            :selected-trace-stats="selectedTraceStats"
            :format-duration="formatDuration"
            @back="clearTraceDetail"
            @load-detail="loadTraceDetail"
            @page-change="loadAdminTraces"
            @refresh="loadAdminTraces(adminTracePage)"
            @refresh-detail="loadTraceDetail"
            @search="searchAdminTraces"
          />
        </template>
        <template v-else-if="currentTab === 'users'">
          <AdminUsersPanel
            v-model:page="userPage"
            v-model:search="userSearch"
            :items="pagedAdminUsers"
            :page-size="tablePageSize"
            :total="filteredAdminUsers.length"
            @create="openUserModal"
            @delete="removeUser"
            @edit="openUserEditModal"
            @refresh="refreshKnowledgeData"
            @role-change="changeUserRole"
          />
        </template>
        <template v-else-if="currentTab === 'sampleQuestions'">
          <AdminSampleQuestionsPanel
            :items="adminSampleQuestions"
            :error="error"
            :clear-error="clearAdminError"
            :create-item="createSampleQuestion"
            :update-item="updateSampleQuestion"
            :delete-item="removeSampleQuestionConfig"
            :refresh="loadSampleQuestions"
          />
        </template>

        <template v-else-if="currentTab === 'settings'">
          <AdminSettingsPanel :cards="settingCards" @refresh="refreshKnowledgeData" />
          <AdminMcpStatusPanel />
        </template>
      </section>
    </main>

    <div v-if="showPipelineModal" class="modal-backdrop" @click.self="closeCreatePipelineModal">
      <AdminPipelineEditorModal
        v-model:description="newPipelineDescription"
        v-model:editor-mode="pipelineEditorMode"
        v-model:json-text="pipelineJsonText"
        v-model:name="newPipelineName"
        v-model:node-drafts="pipelineNodeDrafts"
        :editing-pipeline-id="editingPipelineId"
        :pipeline-node-type-options="pipelineNodeTypeOptions"
        @add-node="addPipelineNode"
        @close="closeCreatePipelineModal"
        @remove-node="removePipelineNode"
        @save="void savePipelineFromModal()"
        @sync-form="syncPipelineFormFromJson"
        @sync-json="syncPipelineJsonFromForm"
        @update-node-config="updatePipelineNodeConfigFromEvent"
      />
    </div>

    <div v-if="activeAdminModal" class="modal-backdrop" @click.self="closeAdminModal">
      <AdminDocumentPreviewModal
        v-if="activeAdminModal === 'documentPreview'"
        :document-preview="documentPreview"
        :loading="documentPreviewLoading"
        @close="closeAdminModal"
      />

      <AdminPipelineNodesModal
        v-else-if="activeAdminModal === 'pipelineNodes'"
        :nodes="selectedPipelineNodes"
        :pipeline-name="selectedPipelineName"
        @close="closeAdminModal"
      />

      <AdminKnowledgeBaseModal
        v-else-if="activeAdminModal === 'knowledgeBase'"
        v-model:collection-name="newKnowledgeCollectionName"
        v-model:embedding-model="newKnowledgeEmbeddingModel"
        v-model:name="newKnowledgeBaseName"
        :editing-knowledge-base-id="editingKnowledgeBaseId"
        :knowledge-embedding-model-options="knowledgeEmbeddingModelOptions"
        @close="closeAdminModal"
        @save="void createKnowledgeBaseFromInput()"
      />

      <AdminDocumentUploadModal
        v-else-if="activeAdminModal === 'uploadDocument'"
        v-model:edit-document-enabled="editDocumentEnabled"
        v-model:edit-document-title="editDocumentTitle"
        v-model:upload-chunk-overlap="uploadChunkOverlap"
        v-model:upload-chunk-size="uploadChunkSize"
        v-model:upload-chunk-strategy="uploadChunkStrategy"
        v-model:upload-pipeline-id="uploadPipelineId"
        v-model:upload-process-mode="uploadProcessMode"
        v-model:upload-recursive-separators-text="uploadRecursiveSeparatorsText"
        v-model:upload-structure-max-chars="uploadStructureMaxChars"
        v-model:upload-structure-min-chars="uploadStructureMinChars"
        :chunk-strategy-options="chunkStrategyOptions"
        :editing-document-id="editingDocumentId"
        :error="error"
        :has-selected-file="Boolean(selectedUploadFile)"
        :ingestion-pipelines="ingestionPipelines"
        :selected-upload-file-label="selectedUploadFileLabel()"
        :upload-accept="uploadAccept"
        :upload-auto-strategy-recommendation="uploadAutoStrategyRecommendation"
        :upload-chunk-summary="uploadChunkSummary"
        :upload-loading="uploadLoading"
        :upload-recursive-separator-summary="uploadRecursiveSeparatorSummary"
        :upload-show-chunk-size-controls="uploadShowChunkSizeControls"
        :upload-show-recursive-separator-controls="uploadShowRecursiveSeparatorControls"
        :upload-show-semantic-notice="uploadShowSemanticNotice"
        @clear-error="clearAdminError"
        @close="closeAdminModal"
        @file-selected="onUploadFileSelected"
        @save="uploadSelectedDocumentFromModal"
      />

      <AdminPipelineTaskModal
        v-else-if="activeAdminModal === 'pipelineTask'"
        v-model:metadata-text="newPipelineTaskMetadataText"
        v-model:pipeline-id="newPipelineTaskPipelineId"
        v-model:source-type="newPipelineTaskSourceType"
        :error="error"
        :ingestion-pipelines="ingestionPipelines"
        :metadata-valid="pipelineTaskMetadataValid()"
        :selected-file="newPipelineTaskFile"
        :upload-accept="uploadAccept"
        :upload-loading="uploadLoading"
        @clear-error="clearAdminError"
        @close="closeAdminModal"
        @file-selected="onPipelineTaskFileSelected"
        @save="void createPipelineTaskFromModal()"
      />

      <AdminChunkEditModal
        v-else-if="activeAdminModal === 'chunkEdit'"
        v-model:content="editChunkContent"
        v-model:enabled="editChunkEnabled"
        @close="closeAdminModal"
        @save="void saveChunkEditFromModal()"
      />

      <AdminIntentNodeModal
        v-else-if="activeAdminModal === 'intent'"
        v-model:advanced="newIntentAdvanced"
        v-model:code="newIntentCode"
        v-model:collection-name="newIntentCollectionName"
        v-model:description="newIntentDescription"
        v-model:knowledge-base-id="newIntentKnowledgeBaseId"
        v-model:level="newIntentLevel"
        v-model:mcp-tool-id="newIntentMcpToolId"
        v-model:name="newIntentName"
        v-model:node-type="newIntentType"
        v-model:parent="newIntentParent"
        v-model:param-prompt="newIntentParamPrompt"
        v-model:prompt="newIntentPrompt"
        v-model:rule-snippet="newIntentRuleSnippet"
        v-model:sample-question="newIntentSampleQuestion"
        v-model:top-k="newIntentTopK"
        v-model:min-score="newIntentMinScore"
        v-model:sort-order="newIntentSortOrder"
        v-model:enabled="newIntentEnabled"
        :admin-intent-nodes="adminIntentNodes"
        :can-save="Boolean(routeProfile)"
        :editing-intent-node-id="editingIntentNodeId"
        :knowledge-bases="knowledgeBases"
        @close="closeAdminModal"
        @save="void createIntentFromInput()"
      />

      <AdminKeywordMappingModal
        v-else-if="activeAdminModal === 'keyword'"
        v-model:enabled="newKeywordEnabled"
        v-model:match-type="newKeywordMatchType"
        v-model:priority="newKeywordPriority"
        v-model:raw-keyword="newKeyword"
        v-model:remark="newKeywordRemark"
        v-model:target-keyword="newKeywordTarget"
        :editing-keyword-mapping-id="editingKeywordMappingId"
        @close="closeAdminModal"
        @save="addKeywordFromInput"
      />

      <AdminUserModal
        v-else-if="activeAdminModal === 'user'"
        v-model:avatar-url="newAdminAvatarUrl"
        v-model:password="newAdminPassword"
        v-model:role="newAdminRole"
        v-model:username="newAdminUsername"
        :editing-user-id="editingUserId"
        @close="closeAdminModal"
        @save="void createAdminUserFromInput()"
      />

    </div>
  </div>
</template>

<style scoped>
.admin-layout {
  --admin-bg: #eef4f8;
  --admin-card: #ffffff;
  --admin-ink: #172033;
  --admin-muted: #5f6f83;
  --admin-border: #d5e1e8;
  --admin-primary: #0f8f82;
  --admin-primary-dark: #0b766d;
  --admin-sidebar: #15202b;
  display: grid;
  flex: 1 1 auto;
  width: 100%;
  min-width: 0;
  min-height: 100vh;
  grid-template-columns: 250px minmax(0, 1fr);
  background: var(--admin-bg);
  color: var(--admin-ink);
  overflow: hidden;
  transition: grid-template-columns 0.2s ease;
}

.admin-layout.collapsed {
  grid-template-columns: 72px minmax(0, 1fr);
}

.admin-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: 28px 14px;
  background: linear-gradient(180deg, #13202a 0%, #182734 100%);
  color: #e8eefc;
  overflow: hidden;
  transition: padding 0.2s ease;
}

.admin-layout.collapsed .admin-sidebar {
  padding-inline: 12px;
}

.admin-brand {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 26px;
}

.brand-copy,
.nav-label,
.nav-section-title {
  transition: opacity 0.15s ease;
}

.admin-layout.collapsed .brand-copy,
.admin-layout.collapsed .nav-label,
.admin-layout.collapsed .nav-section-title {
  display: none;
}

.admin-layout.collapsed .admin-brand,
.admin-layout.collapsed .nav-item {
  justify-content: center;
}

.brand-icon {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: 12px;
  background: var(--admin-primary);
  font-weight: 800;
}

.admin-brand h2 {
  margin: 0;
  font-size: 16px;
}

.admin-brand span,
.nav-section-title {
  color: #aeb8cc;
  font-size: 12px;
}

.nav-section-title {
  margin: 22px 10px 9px;
  font-weight: 700;
}

.settings-title {
  margin-top: 30px;
}

.nav-item,
.collapse-btn {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 11px;
  border: 0;
  border-radius: 10px;
  padding: 10px 11px;
  background: transparent;
  color: #d7def0;
  cursor: pointer;
  font-size: 14px;
  text-align: left;
}

.nav-item.active {
  background: rgba(15, 143, 130, 0.28);
  color: #ffffff;
}

.nav-icon {
  display: inline-flex;
  width: 18px;
  min-width: 18px;
  align-items: center;
  justify-content: center;
  color: currentColor;
  font-size: 15px;
  line-height: 1;
}

.nav-chevron {
  margin-left: auto;
  color: #aeb8cc;
  font-size: 18px;
  line-height: 1;
}

.nav-sub-items {
  display: grid;
  gap: 6px;
  margin: 4px 0 8px 28px;
}

.nav-sub-item {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 9px;
  border: 0;
  border-radius: 9px;
  padding: 8px 10px;
  background: transparent;
  color: #b8c3d9;
  cursor: pointer;
  font-size: 13px;
  text-align: left;
}

.nav-sub-item.active {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
}

.admin-layout.collapsed .nav-sub-items {
  margin-left: 0;
}

.admin-layout.collapsed .nav-sub-item span:last-child {
  display: none;
}

.admin-layout.collapsed .nav-chevron {
  display: none;
}

.collapse-btn {
  position: absolute;
  bottom: 20px;
  left: 14px;
  width: calc(100% - 28px);
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #b7c1d6;
}

.admin-layout.collapsed .collapse-btn {
  left: 14px;
  width: calc(100% - 28px);
  padding-inline: 0;
  font-size: 12px;
}

.admin-main {
  width: 100%;
  min-width: 0;
  overflow: auto;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 28px;
  background: rgba(255, 255, 255, 0.82);
  border-bottom: 1px solid var(--admin-border);
  backdrop-filter: blur(12px);
}

.search-box {
  display: flex;
  align-items: center;
  gap: 12px;
  width: min(380px, 36vw);
  padding: 8px 11px;
  border: 1px solid var(--admin-border);
  border-radius: 10px;
  background: white;
}

.search-box input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  font-size: 14px;
}

kbd {
  padding: 3px 8px;
  border: 1px solid var(--admin-border);
  border-radius: 7px;
  color: var(--admin-muted);
  font-size: 12px;
}

.header-actions,
.page-actions,
.toolbar-actions,
.row-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.toolbar-input {
  width: min(240px, 32vw);
}

.toolbar-select {
  width: 150px;
}

.user-pill {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 12px;
  border: 1px solid var(--admin-border);
  border-radius: 999px;
  background: white;
}

.avatar {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 999px;
  background: #dff4ef;
  color: #2d3445;
  font-weight: 800;
}

.admin-content {
  padding: 28px 28px 44px;
}

.breadcrumb {
  color: #52627c;
  font-size: 14px;
  margin-bottom: 16px;
}

.page-head {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
  margin-bottom: 20px;
}

.page-head h1 {
  margin: 0;
  font-size: 28px;
  line-height: 1.1;
}

.page-head p,
.table-toolbar p,
.placeholder-card p,
.task-card p {
  margin: 6px 0 0;
  color: var(--admin-muted);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}


.metric-card,
.table-card,
.form-panel,
.task-card {
  border: 1px solid var(--admin-border);
  border-radius: 12px;
  background: var(--admin-card);
  box-shadow: 0 8px 24px rgba(34, 43, 63, 0.05);
}

.metric-card {
  padding: 18px;
}

.metric-card span {
  color: var(--admin-muted);
}

.metric-card strong {
  display: block;
  margin-top: 8px;
  font-size: 26px;
}

.table-card {
  overflow: hidden;
}

.table-scroll {
  width: 100%;
  overflow: visible;
}

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--admin-border);
}

.table-toolbar h2,
.placeholder-card h2,
.task-card h2 {
  margin: 0;
  font-size: 18px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 12px;
  line-height: 1.42;
}

.data-table th,
.data-table td {
  padding: 10px 8px;
  border-bottom: 1px solid #e9eef6;
  color: #40506b;
  text-align: left;
  vertical-align: top;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.data-table th {
  background: #fbfcff;
  color: #52627c;
  font-weight: 700;
}

.table-actions-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
  min-width: 0;
}

.data-table button,
.data-table .badge,
.data-table .status-pill {
  white-space: nowrap;
  word-break: keep-all;
  overflow-wrap: normal;
}

.data-table .compact {
  min-height: 28px;
  padding: 0 7px;
  font-size: 12px;
}


.form-panel {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  align-items: end;
  padding: 18px;
  margin-bottom: 20px;
}

.form-panel label {
  display: grid;
  gap: 6px;
  color: #4a5a75;
  font-weight: 700;
}

.form-panel .wide {
  grid-column: 1 / -1;
}

.form-hint {
  color: var(--admin-muted);
  font-size: 13px;
}

.profile-textarea {
  width: 100%;
  min-height: 210px;
  margin-top: 14px;
  padding: 12px;
  line-height: 1.7;
  resize: vertical;
}

.section-gap {
  margin-top: 18px;
}

.muted-line {
  margin: 4px 0 0;
  color: var(--admin-muted);
  font-size: 13px;
  line-height: 1.5;
  white-space: normal;
}


.inline-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  margin-top: 14px;
}

.mapping-form {
  padding: 0 24px 18px;
}

.user-create-form {
  grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr) 140px auto;
  padding: 18px 24px;
  margin-top: 0;
  border-bottom: 1px solid var(--admin-border);
}

.segmented-tabs {
  display: inline-flex;
  gap: 4px;
  border: 1px solid var(--admin-border);
  border-radius: 12px;
  padding: 4px;
  background: #eef3fa;
}

.segmented-tabs button {
  min-height: 34px;
  border: 0;
  border-radius: 9px;
  padding: 0 14px;
  background: transparent;
  color: #52627c;
  cursor: pointer;
  font: inherit;
  font-weight: 800;
}

.segmented-tabs button.active {
  background: white;
  color: var(--admin-primary);
  box-shadow: 0 8px 18px rgba(34, 43, 63, 0.08);
}

.tag-list,
.node-list {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}

.tag-list {
  align-items: start;
  display: flex;
  flex-wrap: wrap;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  border: 1px solid #dbe4f0;
  border-radius: 999px;
  padding: 6px 10px;
  background: #f8fafc;
  color: #334155;
  font-size: 13px;
}

.tag-chip button {
  color: #64748b;
  font-weight: 800;
}

.node-item {
  display: grid;
  gap: 6px;
  border: 1px solid #e5edf7;
  border-radius: 12px;
  padding: 12px;
  background: #fbfdff;
}

.node-item p {
  margin: 0;
  color: #53627a;
  line-height: 1.65;
}

.trace-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}



.ui-input {
  min-height: 42px;
  border: 1px solid var(--admin-border);
  border-radius: 10px;
  padding: 0 12px;
  background: white;
  color: var(--admin-ink);
  font: inherit;
}

textarea.ui-input {
  padding-top: 10px;
}

.primary-btn,
.ghost-btn,
.danger-btn {
  min-height: 42px;
  border-radius: 10px;
  padding: 0 16px;
  border: 1px solid transparent;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
}

.primary-btn {
  background: var(--admin-primary);
  color: white;
}

.primary-btn:hover {
  background: var(--admin-primary-dark);
}

.ghost-btn {
  border-color: var(--admin-border);
  background: white;
  color: #30405b;
}

.danger-btn {
  border-color: #ffd1d1;
  background: #fff5f5;
  color: #d64545;
}

.compact {
  min-height: 34px;
  padding: 0 12px;
  font-size: 13px;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.56;
}

.link-btn {
  border: 0;
  background: transparent;
  color: var(--admin-primary);
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  padding: 0;
}

.link-btn:disabled {
  color: #8794aa;
}

.badge,
.status-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 700;
}

.badge {
  border: 1px solid #dce5f2;
  background: #f0f4fa;
  color: #52627c;
}

.status-pill {
  background: #f1f5f9;
  color: #64748b;
  white-space: nowrap;
}

.status-pill.success {
  background: #e8fbf2;
  color: #059669;
}

.status-pill.warning {
  background: #fff7dc;
  color: #b7791f;
}

.status-pill.danger {
  background: #fff1f1;
  color: #dc2626;
}

.notice-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 0 0 22px;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  padding: 12px 16px;
  background: #eff6ff;
  color: #1d4ed8;
}

.notice-card > span {
  min-width: 0;
  line-height: 1.55;
  word-break: break-word;
}

.notice-card.success {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #15803d;
}

.notice-card.danger {
  border-color: #fecaca;
  background: #fef2f2;
  color: #b91c1c;
}

.notice-close {
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 20px;
  line-height: 1;
}

.notice-close:hover {
  background: rgba(185, 28, 28, 0.09);
}

.placeholder-card,
.task-card {
  padding: 28px;
}

.metric-list {
  display: grid;
  gap: 12px;
}

.metric-list p {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 14px;
  margin: 0;
  padding: 12px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.22);
}

.metric-list p:last-child {
  border-bottom: 0;
}

.metric-list span,
.metric-list small {
  color: var(--admin-muted);
}

.metric-list small {
  grid-column: 1 / -1;
}

.dashboard-hero-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(420px, 1.4fr);
  gap: 18px;
}

.admin-grid-three {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.traffic-stack {
  display: grid;
  gap: 18px;
}

.traffic-row {
  display: grid;
  grid-template-columns: 110px 1fr 54px;
  align-items: center;
  gap: 14px;
}

.traffic-meta {
  display: grid;
  gap: 3px;
}

.traffic-meta span,
.traffic-row small {
  color: var(--admin-muted);
  font-size: 12px;
}

.traffic-bar-track {
  height: 12px;
  overflow: hidden;
  border-radius: 999px;
  background: #e5eaf3;
}

.traffic-bar {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #0f8f82, #2563eb);
  box-shadow: 0 8px 20px rgba(31, 157, 138, 0.24);
}

.dashboard-bars {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(28px, 1fr);
  align-items: end;
  min-height: 260px;
  gap: 10px;
  padding: 18px 10px 4px;
  border-radius: 18px;
  background:
    linear-gradient(rgba(100, 116, 139, 0.08) 1px, transparent 1px) 0 0 / 100% 52px,
    linear-gradient(180deg, rgba(248, 250, 252, 0.95), rgba(241, 245, 249, 0.75));
}

.dashboard-bar-item {
  display: grid;
  grid-template-rows: 1fr auto;
  align-items: end;
  min-width: 0;
  height: 240px;
  gap: 8px;
}

.bar-columns {
  display: flex;
  align-items: end;
  justify-content: center;
  gap: 4px;
  height: 100%;
}

.bar-columns.single span {
  width: 14px;
}

.bar-columns span {
  width: 9px;
  min-height: 4px;
  border-radius: 999px 999px 4px 4px;
}

.bar-session {
  background: linear-gradient(180deg, #22c55e, #15803d);
}

.bar-message {
  background: linear-gradient(180deg, #0f8f82, #0b766d);
}

.bar-latency {
  background: linear-gradient(180deg, #f59e0b, #d97706);
}

.dashboard-bar-item small {
  overflow: hidden;
  color: var(--admin-muted);
  font-size: 11px;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chart-legend {
  display: flex;
  gap: 16px;
  margin-top: 12px;
  color: var(--admin-muted);
  font-size: 12px;
}

.chart-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.chart-legend i {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 999px;
}

.legend-session {
  background: #22c55e;
}

.legend-message {
  background: #0f8f82;
}

.legend-latency {
  background: #f59e0b;
}

.leaderboard-list {
  display: grid;
  gap: 12px;
}

.leaderboard-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}

.leaderboard-row:last-child {
  border-bottom: 0;
}

.leaderboard-row div {
  display: grid;
  gap: 3px;
}

.leaderboard-row small {
  color: var(--admin-muted);
}

.leaderboard-row span {
  min-width: 44px;
  padding: 6px 10px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-weight: 800;
  text-align: center;
}

.insight-list {
  display: grid;
  gap: 10px;
}

.insight-list p,
.insight-item {
  margin: 0;
  padding: 12px 14px;
  border: 1px solid rgba(15, 143, 130, 0.14);
  border-radius: 14px;
  background: rgba(15, 143, 130, 0.05);
  color: var(--admin-ink);
}

.insight-item {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 14px;
}

.insight-item > span {
  align-self: start;
  padding: 5px 9px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.insight-item.success > span {
  background: #dcfce7;
  color: #166534;
}

.insight-item.warning > span {
  background: #fef3c7;
  color: #92400e;
}

.insight-item.danger > span {
  background: #fee2e2;
  color: #991b1b;
}

.insight-item strong,
.insight-item p {
  display: block;
  padding: 0;
  border: 0;
  background: transparent;
}

.insight-item p {
  margin-top: 4px;
  color: var(--admin-muted);
}

.tree-button {
  width: 100%;
  text-align: left;
  cursor: pointer;
}

.tree-button.active {
  border-color: rgba(15, 143, 130, 0.55);
  background: rgba(15, 143, 130, 0.08);
}

.intent-detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.intent-detail-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  color: var(--admin-muted);
  font-size: 13px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.soft-tag {
  padding: 6px 10px;
  border-radius: 999px;
  background: #dff4ef;
  color: #0b766d;
  font-size: 12px;
  font-weight: 700;
}

.table-actions-cell {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 5px;
  min-width: 0;
}

@media (max-width: 1100px) {
  .admin-layout {
    grid-template-columns: 72px minmax(0, 1fr);
  }

  .admin-sidebar {
    position: sticky;
    top: 0;
    height: 100vh;
    padding-inline: 12px;
  }

  .admin-sidebar .brand-copy,
  .admin-sidebar .nav-label,
  .admin-sidebar .nav-section-title {
    display: none;
  }

  .admin-sidebar .admin-brand,
  .admin-sidebar .nav-item {
    justify-content: center;
  }

  .admin-sidebar .nav-chevron {
    display: none;
  }

  .admin-sidebar .nav-sub-items {
    margin-left: 0;
  }

  .admin-sidebar .nav-sub-item {
    justify-content: center;
  }

  .admin-sidebar .nav-sub-item span:last-child {
    display: none;
  }

  .admin-sidebar .collapse-btn {
    left: 14px;
    width: calc(100% - 28px);
    padding-inline: 0;
    font-size: 0;
  }

  .admin-sidebar .collapse-btn::before {
    content: "‹";
    font-size: 18px;
    line-height: 1;
  }

  .admin-main {
    min-width: 0;
  }

  .metric-grid,
  .admin-grid-three,
  .dashboard-hero-grid,
  .form-panel {
    grid-template-columns: 1fr;
  }

  .page-head,
  .table-toolbar,
  .admin-header {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>






