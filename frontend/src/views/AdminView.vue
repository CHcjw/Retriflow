<script setup lang="ts">
import { computed, ref, shallowRef, watch } from "vue";
import { useRouter } from "vue-router";

import AdminDashboardPanel from "../components/admin/AdminDashboardPanel.vue";
import { useRetriFlowAdmin } from "../composables/useRetriFlowAdmin";
import {
  deleteKnowledgeChunk,
  downloadKnowledgeDocumentSource,
  fetchKnowledgeDocumentPreview,
  updateKnowledgeChunk,
  updateKnowledgeChunks,
  type IngestionPipelineNodeConfig,
  type KnowledgeDocumentPreviewResponse
} from "../services/api";
import { useAuthStore } from "../stores/auth";

type AdminTab =
  | "dashboard"
  | "knowledge"
  | "intent"
  | "keyword"
  | "pipeline"
  | "trace"
  | "users"
  | "sampleQuestions"
  | "settings";
type KnowledgeStage = "chunks" | "documents" | "knowledge-bases";
type SettingCard = {
  title: string;
  items: Array<{ label: string; value: string }>;
};

const router = useRouter();
const authStore = useAuthStore();

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

const currentTab = shallowRef<AdminTab>("knowledge");
const knowledgeStage = shallowRef<KnowledgeStage>("knowledge-bases");
const knowledgeSearch = shallowRef("");
const documentSearch = shallowRef("");
const documentStatusFilter = shallowRef("all");
const chunkStatusFilter = shallowRef("all");
const selectedChunkIds = ref<number[]>([]);
const newKnowledgeBaseName = shallowRef("");
const selectedUploadFileName = shallowRef("");
const selectedUploadFile = shallowRef<File | null>(null);
const showCreateKbPanel = shallowRef(false);
const showUploadPanel = shallowRef(false);
const sidebarCollapsed = shallowRef(false);
const newKeyword = shallowRef("");
const newKeywordTarget = shallowRef("");
const newKeywordMatchType = shallowRef("exact");
const newKeywordPriority = shallowRef(0);
const newKeywordEnabled = shallowRef("enabled");
const newKeywordRemark = shallowRef("");
const newSampleQuestion = shallowRef("");
const newSampleTitle = shallowRef("");
const newSampleDescription = shallowRef("");
const pipelineSearch = shallowRef("");
const ingestionTaskStatusFilter = shallowRef("all");
const newPipelineTaskPipelineId = shallowRef<number | null>(null);
const newPipelineTaskSourceType = shallowRef("local_file");
const newPipelineTaskFile = shallowRef<File | null>(null);
const newPipelineTaskFileInput = ref<HTMLInputElement | null>(null);
const newPipelineTaskMetadataText = shallowRef('{"source":"manual"}');
const intentSearch = shallowRef("");
const intentMode = shallowRef<"list" | "tree">("tree");
const selectedIntentNodeId = shallowRef("");
const keywordSearch = shallowRef("");
const sampleQuestionSearch = shallowRef("");
const pipelineTab = shallowRef<"pipelines" | "tasks">("pipelines");
const pipelineMenuOpen = shallowRef(false);
const userSearch = shallowRef("");
const newAdminUsername = shallowRef("");
const newAdminPassword = shallowRef("");
const newAdminRole = shallowRef("user");
const newAdminAvatarUrl = shallowRef("");
const editingKnowledgeBaseId = shallowRef("");
const editingDocumentId = shallowRef<number | null>(null);
const editingChunkId = shallowRef<number | null>(null);
const editingUserId = shallowRef("");
const editDocumentTitle = shallowRef("");
const editDocumentEnabled = shallowRef(true);
const editChunkContent = shallowRef("");
const editChunkEnabled = shallowRef(true);
const inlineUploadFileInput = ref<HTMLInputElement | null>(null);
const modalUploadFileInput = ref<HTMLInputElement | null>(null);
const documentPreviewLoading = shallowRef(false);
const documentPreview = shallowRef<KnowledgeDocumentPreviewResponse | null>(null);
const activeAdminModal = shallowRef<
  | "chunkEdit"
  | "documentPreview"
  | "intent"
  | "keyword"
  | "knowledgeBase"
  | "pipeline"
  | "pipelineNodes"
  | "pipelineTask"
  | "sampleQuestion"
  | "uploadDocument"
  | "user"
  | null
>(null);

const newIntentName = shallowRef("");
const newIntentCode = shallowRef("");
const newIntentLevel = shallowRef("CATEGORY");
const newIntentType = shallowRef("KB");
const newIntentParent = shallowRef("ROOT");
const newIntentKnowledgeBaseId = shallowRef("");
const newIntentCollectionName = shallowRef("");
const newIntentDescription = shallowRef("");
const newIntentSampleQuestion = shallowRef("");
const newIntentRuleSnippet = shallowRef("");
const newIntentPrompt = shallowRef("");
const newIntentAdvanced = shallowRef("");
const newIntentTopK = shallowRef<number | null>(5);
const newIntentSortOrder = shallowRef(0);
const newIntentEnabled = shallowRef(true);
const editingIntentNodeId = shallowRef("");
const editingKeywordMappingId = shallowRef("");

function parseLines(value: string): string[] {
  return value
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean);
}

function parseUploadRecursiveSeparators(value: string): string[] {
  return value
    .split(/\r?\n/u)
    .map((rawLine) => {
      if (rawLine === " " || rawLine === "[space]") {
        return " ";
      }
      const trimmed = rawLine.trim();
      if (!trimmed) {
        return null;
      }
      if (trimmed === "\\n\\n") {
        return "\n\n";
      }
      if (trimmed === "\\n") {
        return "\n";
      }
      if (trimmed === "\\t" || trimmed === "[tab]") {
        return "\t";
      }
      return rawLine;
    })
    .filter((separator): separator is string => separator !== null);
}

function buildUploadChunkConfig() {
  if (uploadChunkStrategy.value === "fixed_size") {
    return {
      chunkSize: uploadChunkSize.value,
      overlapSize: uploadChunkOverlap.value
    };
  }
  if (uploadChunkStrategy.value === "structure_aware") {
    return {
      targetChars: uploadChunkSize.value,
      overlapChars: uploadChunkOverlap.value,
      maxChars: uploadStructureMaxChars.value,
      minChars: uploadStructureMinChars.value
    };
  }
  if (["recursive", "hybrid_recursive_semantic"].includes(uploadChunkStrategy.value)) {
    return {
      chunk_size: uploadChunkSize.value,
      chunk_overlap: uploadChunkOverlap.value,
      recursive_separators: parseUploadRecursiveSeparators(uploadRecursiveSeparatorsText.value)
    };
  }
  return {
    chunk_size: uploadChunkSize.value,
    chunk_overlap: uploadChunkOverlap.value
  };
}

const knowledgeEmbeddingModelOptions = [
  { label: "siliconflow · Qwen/Qwen3-Embedding-8B", value: "Qwen/Qwen3-Embedding-8B" },
  { label: "ollama · qwen3-embedding:8b", value: "qwen3-embedding:8b" }
] as const;
const newKnowledgeEmbeddingModel = shallowRef("Qwen/Qwen3-Embedding-8B");
const newKnowledgeCollectionName = shallowRef("");

const uploadAccept = ".txt,.md,.pdf,.doc,.docx,.xls,.xlsx,.html,.htm,text/plain,text/markdown,application/pdf";
const tablePageSize = 10;
const knowledgeBasePage = shallowRef(1);
const documentPage = shallowRef(1);
const chunkPage = shallowRef(1);
const realIntentPage = shallowRef(1);
const keywordPage = shallowRef(1);
const pipelinePage = shallowRef(1);
const ingestionTaskPage = shallowRef(1);
const tracePage = shallowRef(1);
const userPage = shallowRef(1);
const sampleQuestionPage = shallowRef(1);

function totalPages(total: number) {
  return Math.max(1, Math.ceil(total / tablePageSize));
}

function pageSlice<T>(items: T[], page: number) {
  const currentPage = Math.min(Math.max(1, page), totalPages(items.length));
  const start = (currentPage - 1) * tablePageSize;
  return items.slice(start, start + tablePageSize);
}

function paginationLabel(total: number, page: number) {
  return `第 ${Math.min(Math.max(1, page), totalPages(total))} / ${totalPages(total)} 页，共 ${total} 条`;
}

function previousPage(page: number) {
  return Math.max(1, page - 1);
}

function nextPage(page: number, total: number) {
  return Math.min(totalPages(total), page + 1);
}

const dashboardStats = computed(() => ({
  knowledgeBaseCount: knowledgeBases.value.length,
  documentCount: knowledgeBases.value.reduce((sum, item) => sum + item.document_count, 0),
  indexedDocumentCount: documents.value.filter((item) => item.vector_index_status === "indexed").length,
  chunkCount: documents.value.reduce((sum, item) => sum + item.vector_chunk_count, 0)
}));

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

const legacyPipelineRows = computed(() => [
  {
    name: "retriflow-ingestion-pipeline",
    description: "文档摄取流水线 - Tika 解析、结构化清洗、分块、向量化",
    nodeCount: 5,
    owner: "admin",
    updatedAt: ingestionTasks.value[0]?.created_at || selectedKnowledgeBase.value?.updated_at || "",
    taskCount: ingestionTasks.value.length
  }
]);

void legacyPipelineRows;

const showPipelineModal = shallowRef(false);
const editingPipelineId = shallowRef<number | null>(null);
const selectedPipelineNodes = ref<IngestionPipelineNodeConfig[]>([]);
const selectedPipelineName = shallowRef("");
const pipelineEditorMode = shallowRef<"form" | "json">("form");
const newPipelineName = shallowRef("");
const newPipelineDescription = shallowRef("");
const pipelineJsonText = shallowRef("[]");
const pipelineNodeDrafts = ref<IngestionPipelineNodeConfig[]>([]);

const pipelineNodeTypeOptions = [
  "fetcher",
  "parser",
  "extractor",
  "cleaner",
  "validator",
  "chunker",
  "embedder",
  "indexer",
  "llm_router",
  "custom"
];

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

const intentRows = computed(() => {
  const profile = routeProfile.value;
  if (!selectedKnowledgeBase.value || !profile) {
    return [];
  }
  return [
    {
      id: selectedKnowledgeBase.value.id,
      name: selectedKnowledgeBase.value.name,
      level: "DOMAIN",
      type: "KB",
      path: selectedKnowledgeBase.value.name,
      resource: `${selectedKnowledgeBase.value.collection_name || selectedKnowledgeBase.value.id} · TopK: 全局默认`,
      sampleCount: profile.sample_questions.length,
      status: "启用"
    },
    ...profile.sample_questions.map((question, index) => ({
      id: `${selectedKnowledgeBase.value?.id || "kb"}-sample-${index + 1}`,
      name: question,
      level: "CATEGORY",
      type: "KB",
      path: `${selectedKnowledgeBase.value?.name || "-"} / ${question}`,
      resource: `${selectedKnowledgeBase.value?.collection_name || selectedKnowledgeBase.value?.id || "-"} · TopK: 全局默认`,
      sampleCount: 1,
      status: "启用"
    }))
  ].filter((item) => {
    const query = intentSearch.value.trim().toLowerCase();
    return !query || item.name.toLowerCase().includes(query) || item.id.toLowerCase().includes(query);
  });
});

const pagedIntentRows = computed(() => pageSlice(intentRows.value, realIntentPage.value));

const keywordRows = computed(() => {
  const keywords = routeProfile.value?.keywords ?? [];
  return keywords
    .map((keyword) => ({
      raw: keyword,
      target: selectedKnowledgeBase.value?.name || keyword,
      matchType: "精确匹配",
      priority: 0,
      status: "启用",
      remark: `路由到 ${selectedKnowledgeBase.value?.id || "-"}`,
      updatedAt: routeProfile.value?.updated_at || ""
    }))
    .filter((item) => {
      const query = keywordSearch.value.trim().toLowerCase();
      return !query || item.raw.toLowerCase().includes(query) || item.target.toLowerCase().includes(query);
    });
});

const realIntentRows = computed(() => {
  const query = intentSearch.value.trim().toLowerCase();
  return adminIntentNodes.value
    .map((node) => {
      const kb = knowledgeBases.value.find((item) => item.id === node.knowledge_base_id);
      const parent = adminIntentNodes.value.find((item) => item.id === node.parent_id);
      return {
        ...node,
        type: node.node_type,
        path: `${parent?.name ?? "ROOT"} / ${node.name}`,
        resource: kb?.name || node.collection_name || node.knowledge_base_id || "-",
        sampleCount: node.sample_questions.length,
        status: node.enabled ? "启用" : "停用"
      };
    })
    .filter((item) => {
      return (
        !query ||
        item.name.toLowerCase().includes(query) ||
        item.code.toLowerCase().includes(query) ||
        item.id.toLowerCase().includes(query)
      );
    });
});

const pagedRealIntentRows = computed(() => pageSlice(realIntentRows.value, realIntentPage.value));

const selectedIntentNode = computed(() =>
  adminIntentNodes.value.find((item) => item.id === selectedIntentNodeId.value) ?? adminIntentNodes.value[0] ?? null
);

const rootIntentNodes = computed(() =>
  adminIntentNodes.value
    .filter((item) => item.parent_id === "ROOT")
    .sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name))
);

function childIntentNodes(parentId: string) {
  return adminIntentNodes.value
    .filter((item) => item.parent_id === parentId)
    .sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name));
}

function intentNodeLevelClass(level: string) {
  return `level-${level.toLowerCase()}`;
}

function intentNodeTypeClass(type: string) {
  return `type-${type.toLowerCase()}`;
}

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

const sampleQuestionRows = computed(() => {
  return adminSampleQuestions.value
    .map((sample) => {
      return {
        id: sample.id,
        title: sample.title,
        description: sample.description,
        question: sample.question,
        updatedAt: sample.updated_at
      };
    })
    .filter((item) => {
      const query = sampleQuestionSearch.value.trim().toLowerCase();
      return !query || item.title.toLowerCase().includes(query) || item.description.toLowerCase().includes(query) || item.question.toLowerCase().includes(query);
    });
});

const pagedSampleQuestionRows = computed(() => pageSlice(sampleQuestionRows.value, sampleQuestionPage.value));

const traceStats = computed(() => {
  const total = adminTraceTotal.value;
  const success = total;
  const failed = 0;
  const running = 0;
  const successRate = total > 0 ? Math.round((success / total) * 100) : 0;
  const durations = adminTraces.value.map((trace) => trace.duration_ms).filter((duration) => duration > 0);
  const averageDuration = durations.length > 0 ? Math.round(durations.reduce((sum, item) => sum + item, 0) / durations.length) : 0;
  const sortedDurations = [...durations].sort((a, b) => a - b);
  const p95Index = sortedDurations.length > 0 ? Math.min(sortedDurations.length - 1, Math.ceil(sortedDurations.length * 0.95) - 1) : 0;
  const p95Duration = sortedDurations[p95Index] ?? 0;
  return {
    total,
    success,
    failed,
    running,
    successRate,
    averageMs: durations.length > 0 ? formatDuration(averageDuration) : "-",
    p95Ms: durations.length > 0 ? formatDuration(p95Duration) : "-"
  };
});

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
  const userMessages = messages.filter((message) => message.role === "user").length;
  const assistantMessages = messages.filter((message) => message.role === "assistant").length;
  return {
    nodeCount: Math.max(messages.length, 1),
    successCount: messages.length,
    failedCount: 0,
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

watch([sampleQuestionSearch], () => {
  sampleQuestionPage.value = 1;
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
      { label: "Rerank Provider", value: settingValue("rerank_provider") }
    ]
  },
  {
    title: "模型选择策略",
    items: [
      { label: "Chat Model", value: settingValue("default_chat_model") },
      { label: "Deep Thinking", value: settingValue("deep_thinking_model") },
      { label: "Embedding Model", value: settingValue("default_embedding_model") },
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

const breadcrumbItems = computed(() => {
  if (currentTab.value === "pipeline") {
    return ["首页", "数据通道", pipelineTab.value === "pipelines" ? "流水线管理" : "流水线任务"];
  }
  if (currentTab.value !== "knowledge") {
    return ["首页", navItems.value.find((item) => item.key === currentTab.value)?.label ?? "后台"];
  }
  if (knowledgeStage.value === "knowledge-bases") {
    return ["首页", "知识库管理"];
  }
  if (knowledgeStage.value === "documents") {
    return ["首页", "知识库管理", "文档管理"];
  }
  return ["首页", "知识库管理", "文档管理", "切块管理"];
});

const navItems = computed<Array<{ key: AdminTab; label: string; group: "main" | "settings" }>>(() => [
  { key: "dashboard", label: "Dashboard", group: "main" },
  { key: "knowledge", label: "知识库管理", group: "main" },
  { key: "intent", label: "意图管理", group: "main" },
  { key: "keyword", label: "关键词映射", group: "main" },
  { key: "pipeline", label: "数据通道", group: "main" },
  { key: "trace", label: "链路追踪", group: "main" },
  { key: "users", label: "用户管理", group: "settings" },
  { key: "sampleQuestions", label: "示例问题", group: "settings" },
  { key: "settings", label: "系统设置", group: "settings" }
]);

const navIconMap: Record<AdminTab, string> = {
  dashboard: "▦",
  knowledge: "▣",
  intent: "◇",
  keyword: "⌕",
  pipeline: "⇧",
  trace: "⛓",
  users: "♙",
  sampleQuestions: "?",
  settings: "⚙"
};

const pipelineNavItems = [
  { key: "pipelines" as const, label: "流水线管理", icon: "▣" },
  { key: "tasks" as const, label: "流水线任务", icon: "▤" }
];

function activateTab(tab: AdminTab) {
  if (tab === "pipeline") {
    pipelineMenuOpen.value = !pipelineMenuOpen.value;
    return;
  }
  currentTab.value = tab;
  pipelineMenuOpen.value = false;
  if (tab === "knowledge" && !selectedKnowledgeBaseId.value) {
    knowledgeStage.value = "knowledge-bases";
  }
}

function activatePipelineTab(tab: "pipelines" | "tasks") {
  currentTab.value = "pipeline";
  pipelineTab.value = tab;
  pipelineMenuOpen.value = true;
}

function closeAdminModal() {
  activeAdminModal.value = null;
}

function clearAdminError() {
  error.value = "";
}

function openKnowledgeBaseModal() {
  editingKnowledgeBaseId.value = "";
  newKnowledgeBaseName.value = "";
  newKnowledgeEmbeddingModel.value = "Qwen/Qwen3-Embedding-8B";
  newKnowledgeCollectionName.value = "";
  activeAdminModal.value = "knowledgeBase";
}

function openKnowledgeBaseEditModal(knowledgeBaseId: string) {
  const knowledgeBase = knowledgeBases.value.find((item) => item.id === knowledgeBaseId);
  if (!knowledgeBase) {
    return;
  }
  editingKnowledgeBaseId.value = knowledgeBase.id;
  newKnowledgeBaseName.value = knowledgeBase.name;
  newKnowledgeEmbeddingModel.value = knowledgeBase.embedding_model;
  newKnowledgeCollectionName.value = knowledgeBase.collection_name;
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
  if (modalUploadFileInput.value) {
    modalUploadFileInput.value.value = "";
  }
  activeAdminModal.value = "uploadDocument";
}

function openPipelineTaskModal() {
  newPipelineTaskPipelineId.value = ingestionPipelines.value[0]?.id ?? null;
  newPipelineTaskSourceType.value = "local_file";
  newPipelineTaskFile.value = null;
  newPipelineTaskMetadataText.value = '{"source":"manual"}';
  if (newPipelineTaskFileInput.value) {
    newPipelineTaskFileInput.value.value = "";
  }
  activeAdminModal.value = "pipelineTask";
}

function onPipelineTaskFileSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  newPipelineTaskFile.value = input.files?.[0] ?? null;
}

function pipelineTaskMetadataValid() {
  if (!newPipelineTaskMetadataText.value.trim()) {
    return true;
  }
  try {
    JSON.parse(newPipelineTaskMetadataText.value);
    return true;
  } catch {
    return false;
  }
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
  newPipelineTaskFile.value = null;
  if (newPipelineTaskFileInput.value) {
    newPipelineTaskFileInput.value.value = "";
  }
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
  uploadRecursiveSeparatorsText.value = Array.isArray(config.recursiveSeparators)
    ? config.recursiveSeparators.map((separator) => (separator === " " ? "[space]" : separator.replace(/\n/gu, "\\n").replace(/\t/gu, "\\t"))).join("\n")
    : uploadRecursiveSeparatorsText.value;
  selectedUploadFile.value = null;
  selectedUploadFileName.value = document.source_uri || document.title;
  if (modalUploadFileInput.value) {
    modalUploadFileInput.value.value = "";
  }
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
  editingKeywordMappingId.value = "";
  newKeyword.value = "";
  newKeywordTarget.value = "";
  newKeywordMatchType.value = "exact";
  newKeywordPriority.value = 0;
  newKeywordEnabled.value = "enabled";
  newKeywordRemark.value = "";
  activeAdminModal.value = "keyword";
}

function openKeywordEditModal(mappingId: string) {
  const mapping = adminKeywordMappings.value.find((item) => item.id === mappingId);
  if (!mapping) {
    return;
  }
  editingKeywordMappingId.value = mapping.id;
  newKeyword.value = mapping.raw_keyword;
  newKeywordTarget.value = mapping.target_keyword;
  newKeywordMatchType.value = mapping.match_type;
  newKeywordPriority.value = mapping.priority;
  newKeywordEnabled.value = mapping.enabled ? "enabled" : "disabled";
  newKeywordRemark.value = mapping.remark;
  activeAdminModal.value = "keyword";
}

function openSampleQuestionModal() {
  newSampleTitle.value = selectedKnowledgeBase.value?.name || "";
  newSampleDescription.value = "知识库推荐问法";
  newSampleQuestion.value = "";
  activeAdminModal.value = "sampleQuestion";
}

function openUserModal() {
  editingUserId.value = "";
  newAdminUsername.value = "";
  newAdminPassword.value = "";
  newAdminRole.value = "user";
  newAdminAvatarUrl.value = "";
  activeAdminModal.value = "user";
}

function openUserEditModal(userId: string) {
  const user = adminUsers.value.find((item) => item.id === userId);
  if (!user) {
    return;
  }
  editingUserId.value = user.id;
  newAdminUsername.value = user.username;
  newAdminPassword.value = "";
  newAdminRole.value = user.role;
  newAdminAvatarUrl.value = user.avatar_url;
  activeAdminModal.value = "user";
}

function openIntentModal() {
  editingIntentNodeId.value = "";
  newIntentName.value = "";
  newIntentCode.value = "";
  newIntentLevel.value = "CATEGORY";
  newIntentType.value = "KB";
  newIntentParent.value = "ROOT";
  newIntentKnowledgeBaseId.value = selectedKnowledgeBaseId.value;
  newIntentCollectionName.value = selectedKnowledgeBase.value?.collection_name || "";
  newIntentDescription.value = "";
  newIntentSampleQuestion.value = "";
  newIntentRuleSnippet.value = "";
  newIntentPrompt.value = "";
  newIntentTopK.value = 5;
  newIntentSortOrder.value = 0;
  newIntentEnabled.value = true;
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
  editingIntentNodeId.value = node.id;
  selectedIntentNodeId.value = node.id;
  newIntentName.value = node.name;
  newIntentCode.value = node.code;
  newIntentLevel.value = node.level;
  newIntentType.value = node.node_type;
  newIntentParent.value = node.parent_id;
  newIntentKnowledgeBaseId.value = node.knowledge_base_id;
  newIntentCollectionName.value = node.collection_name;
  newIntentDescription.value = node.description;
  newIntentSampleQuestion.value = node.sample_questions.join("\n");
  newIntentRuleSnippet.value = node.rule_snippet;
  newIntentPrompt.value = node.prompt_template;
  newIntentTopK.value = node.top_k ?? 5;
  newIntentSortOrder.value = node.sort_order;
  newIntentEnabled.value = node.enabled;
  activeAdminModal.value = "intent";
}

function locateIntentNode(nodeId: string) {
  selectedIntentNodeId.value = nodeId;
  intentMode.value = "tree";
}

async function deleteIntentNodeFromInput(nodeId: string) {
  await removeIntentNode(nodeId);
  if (selectedIntentNodeId.value === nodeId) {
    selectedIntentNodeId.value = adminIntentNodes.value[0]?.id ?? "";
  }
}

async function addKeywordFromInput() {
  if (!newKeyword.value.trim()) {
    return;
  }
  const payload = {
    raw_keyword: newKeyword.value.trim(),
    target_keyword: newKeywordTarget.value.trim() || newKeyword.value.trim(),
    match_type: newKeywordMatchType.value,
    priority: Number(newKeywordPriority.value) || 0,
    enabled: newKeywordEnabled.value === "enabled",
    remark: newKeywordRemark.value.trim(),
    knowledge_base_id: selectedKnowledgeBaseId.value
  };
  if (editingKeywordMappingId.value) {
    await updateKeywordMapping(editingKeywordMappingId.value, payload);
  } else {
    await createKeywordMapping(payload);
  }
  newKeyword.value = "";
  newKeywordTarget.value = "";
  closeAdminModal();
}

async function addSampleQuestionFromInput() {
  const question = newSampleQuestion.value.trim();
  if (!question) {
    return;
  }
  await createSampleQuestion({
    title: newSampleTitle.value.trim() || "示例问题",
    description: newSampleDescription.value.trim(),
    question,
    sort_order: adminSampleQuestions.value.length * 10 + 10,
    enabled: true
  });
  newSampleTitle.value = "";
  newSampleDescription.value = "";
  newSampleQuestion.value = "";
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

function removeSampleQuestionByValue(sampleId: string) {
  const sample = adminSampleQuestions.value.find((item) => item.id === sampleId || item.question === sampleId);
  if (sample) {
    void removeSampleQuestionConfig(sample.id);
  }
}

async function createAdminUserFromInput() {
  if (editingUserId.value) {
    if (!newAdminUsername.value.trim()) {
      return;
    }
    await saveUser(editingUserId.value, {
      username: newAdminUsername.value.trim(),
      role: newAdminRole.value,
      avatar_url: newAdminAvatarUrl.value.trim()
    });
    closeAdminModal();
    return;
  }
  if (!newAdminUsername.value.trim() || !newAdminPassword.value.trim()) {
    return;
  }
  await createUser({
    username: newAdminUsername.value.trim(),
    password: newAdminPassword.value,
    role: newAdminRole.value
  });
  newAdminUsername.value = "";
  newAdminPassword.value = "";
  newAdminRole.value = "user";
  newAdminAvatarUrl.value = "";
  closeAdminModal();
}

async function createKnowledgeBaseFromInput() {
  if (!newKnowledgeBaseName.value.trim()) {
    return;
  }
  if (editingKnowledgeBaseId.value) {
    const updated = await saveKnowledgeBase(editingKnowledgeBaseId.value, {
      name: newKnowledgeBaseName.value.trim(),
      embeddingModel: newKnowledgeEmbeddingModel.value,
      collectionName: newKnowledgeCollectionName.value.trim()
    });
    if (updated) {
      closeAdminModal();
    }
    return;
  }
  await addKnowledgeBase({
    name: newKnowledgeBaseName.value.trim(),
    embeddingModel: newKnowledgeEmbeddingModel.value,
    collectionName: newKnowledgeCollectionName.value.trim()
  });
  newKnowledgeBaseName.value = "";
  newKnowledgeEmbeddingModel.value = "Qwen/Qwen3-Embedding-8B";
  newKnowledgeCollectionName.value = "";
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
    chunkConfig: buildUploadChunkConfig()
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
  if (modalUploadFileInput.value) {
    modalUploadFileInput.value.value = "";
  }
  closeAdminModal();
  await refreshKnowledgeData();
}

async function createIntentFromInput() {
  if (!newIntentName.value.trim()) {
    return;
  }
  const payload = {
    name: newIntentName.value.trim(),
    code: newIntentCode.value.trim() || newIntentName.value.trim().toLowerCase().replace(/\s+/gu, "_"),
    level: newIntentLevel.value,
    node_type: newIntentType.value,
    parent_id: newIntentParent.value || "ROOT",
    knowledge_base_id: newIntentKnowledgeBaseId.value,
    collection_name: newIntentCollectionName.value.trim(),
    description: newIntentDescription.value.trim(),
    sample_questions: parseLines(newIntentSampleQuestion.value),
    rule_snippet: newIntentRuleSnippet.value.trim(),
    prompt_template: newIntentPrompt.value.trim(),
    top_k: newIntentTopK.value,
    sort_order: Number(newIntentSortOrder.value) || 0,
    enabled: newIntentEnabled.value
  };
  const saved = editingIntentNodeId.value
    ? await updateIntentNode(editingIntentNodeId.value, payload)
    : await createIntentNode(payload);
  if (saved) {
    selectedIntentNodeId.value = saved.id;
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

function formatDate(value: string) {
  if (!value || value === "None") {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function formatDuration(value: number | string | null | undefined) {
  const ms = typeof value === "number" ? value : Number(value || 0);
  if (!Number.isFinite(ms) || ms <= 0) {
    return "0ms";
  }
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  return `${Math.round(ms)}ms`;
}

function statusLabel(status: string) {
  if (status === "indexing") {
    return "切块中";
  }
  if (status === "indexed") {
    return "切块成功";
  }
  if (status === "failed") {
    return "切块失败";
  }
  if (status === "pending") {
    return "待切块";
  }
  return status || "未知";
}

function statusClass(status: string) {
  return {
    success: status === "indexed",
    danger: status === "failed",
    warning: status === "pending" || status === "indexing"
  };
}

function sourceLabel(sourceType: string) {
  return sourceType || "local";
}

function createDefaultPipelineNode(index = pipelineNodeDrafts.value.length): IngestionPipelineNodeConfig {
  return {
    node_id: `node-${index + 1}`,
    node_type: index === 0 ? "fetcher" : "custom",
    next_node_id: "",
    condition: "",
    config: {}
  };
}

function stringifyPipelineNodes(nodes: IngestionPipelineNodeConfig[]) {
  return JSON.stringify(nodes, null, 2);
}

function resetPipelineForm() {
  editingPipelineId.value = null;
  newPipelineName.value = "";
  newPipelineDescription.value = "";
  pipelineEditorMode.value = "form";
  pipelineNodeDrafts.value = [
    { ...createDefaultPipelineNode(0), node_type: "parser", next_node_id: "node-2", config: { parser: "apache-tika" } },
    { ...createDefaultPipelineNode(1), node_type: "chunker", next_node_id: "node-3", config: { strategy: "auto" } },
    { ...createDefaultPipelineNode(2), node_type: "indexer", config: { vector_store: "pgvector" } }
  ];
  pipelineJsonText.value = stringifyPipelineNodes(pipelineNodeDrafts.value);
}

function openCreatePipelineModal() {
  resetPipelineForm();
  showPipelineModal.value = true;
}

function openEditPipelineModal(pipeline: { id: number; name: string; description: string; nodes: IngestionPipelineNodeConfig[] }) {
  editingPipelineId.value = pipeline.id;
  newPipelineName.value = pipeline.name;
  newPipelineDescription.value = pipeline.description === "-" ? "" : pipeline.description;
  pipelineEditorMode.value = "form";
  pipelineNodeDrafts.value = pipeline.nodes.map((node) => ({
    node_id: node.node_id,
    node_type: node.node_type,
    next_node_id: node.next_node_id,
    condition: node.condition,
    config: { ...node.config }
  }));
  pipelineJsonText.value = stringifyPipelineNodes(pipelineNodeDrafts.value);
  showPipelineModal.value = true;
}

function openPipelineNodesModal(pipeline: { name: string; nodes: IngestionPipelineNodeConfig[] }) {
  selectedPipelineName.value = pipeline.name;
  selectedPipelineNodes.value = pipeline.nodes;
  activeAdminModal.value = "pipelineNodes";
}

function closeCreatePipelineModal() {
  showPipelineModal.value = false;
  editingPipelineId.value = null;
}

function addPipelineNode() {
  pipelineNodeDrafts.value = [...pipelineNodeDrafts.value, createDefaultPipelineNode()];
  pipelineJsonText.value = stringifyPipelineNodes(pipelineNodeDrafts.value);
}

function removePipelineNode(index: number) {
  pipelineNodeDrafts.value = pipelineNodeDrafts.value.filter((_, itemIndex) => itemIndex !== index);
  pipelineJsonText.value = stringifyPipelineNodes(pipelineNodeDrafts.value);
}

function updatePipelineNodeConfig(index: number, rawConfig: string) {
  try {
    const parsed = rawConfig.trim() ? JSON.parse(rawConfig) : {};
    if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
      pipelineNodeDrafts.value[index].config = parsed as Record<string, unknown>;
    }
  } catch {
    // Keep the last valid config while the user is still typing JSON.
  }
}

function updatePipelineNodeConfigFromEvent(index: number, event: Event) {
  updatePipelineNodeConfig(index, (event.target as HTMLTextAreaElement).value);
}

function syncPipelineJsonFromForm() {
  pipelineJsonText.value = stringifyPipelineNodes(pipelineNodeDrafts.value);
  pipelineEditorMode.value = "json";
}

function syncPipelineFormFromJson() {
  try {
    const parsed = JSON.parse(pipelineJsonText.value) as IngestionPipelineNodeConfig[];
    if (Array.isArray(parsed)) {
      pipelineNodeDrafts.value = parsed.map((node, index) => ({
        node_id: String(node.node_id || `node-${index + 1}`),
        node_type: String(node.node_type || "custom"),
        next_node_id: String(node.next_node_id || ""),
        condition: String(node.condition || ""),
        config: typeof node.config === "object" && node.config !== null && !Array.isArray(node.config) ? node.config : {}
      }));
    }
  } catch {
    return;
  }
  pipelineEditorMode.value = "form";
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

function processingModeLabel(mode: string) {
  const labels: Record<string, string> = {
    auto: "自动处理",
    chunk_strategy: "按切块策略处理",
    data_channel: "按数据通道处理",
    structure_aware: "结构感知分块",
    fixed: "固定分块",
    fixed_size: "固定大小分块",
    overlap: "重叠分块",
    recursive: "递归分块",
    semantic_embedding: "Embedding 语义分块",
    semantic_llm: "LLM 语义分块",
    hybrid_recursive_semantic: "递归 + 语义",
    hybrid_by_document_type: "按类型策略",
    hybrid_postprocess: "分块后处理"
  };
  return labels[mode] ?? mode ?? "自动处理";
}

function documentTypeLabel(type: string) {
  const labels: Record<string, string> = {
    manual: "普通文本",
    knowledge_base: "知识库文档",
    faq: "FAQ",
    contract: "合同",
    log: "日志",
    table: "表格",
    ocr: "OCR 文档",
    mixed_knowledge: "混合知识"
  };
  return labels[type] ?? type ?? "知识库文档";
}

function chunkMetadataSummary(metadata: Record<string, unknown>) {
  const parts = [
    metadata.block_type ? `块类型：${String(metadata.block_type)}` : "",
    metadata.page_number ? `页码：${String(metadata.page_number)}` : "",
    metadata.heading_path ? `标题：${Array.isArray(metadata.heading_path) ? metadata.heading_path.join(" / ") : String(metadata.heading_path)}` : ""
  ].filter(Boolean);
  return parts.join(" · ") || "正文分块";
}
</script>

<template>
  <div class="admin-layout" :class="{ collapsed: sidebarCollapsed }">
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

      <button class="collapse-btn" type="button" @click="sidebarCollapsed = !sidebarCollapsed">
        {{ sidebarCollapsed ? "展开" : "收起侧边栏" }}
      </button>
    </aside>

    <main class="admin-main">
      <header class="admin-header">
        <div class="search-box">
          <span>⌕</span>
          <input
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

        <p v-if="readonlyNotice" class="notice-card">{{ readonlyNotice }}</p>
        <div v-if="error" class="notice-card danger notice-card-dismissible">
          <span>{{ error }}</span>
          <button class="notice-close" type="button" aria-label="关闭错误提示" @click="clearAdminError">
            ×
          </button>
        </div>

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

          <section v-if="knowledgeStage === 'knowledge-bases'" class="table-card">
            <div class="table-scroll">
            <table class="data-table kb-table">
              <thead>
                <tr>
                  <th>名称</th>
                  <th>Embedding 模型</th>
                  <th>Collection</th>
                  <th>文档数</th>
                  <th>负责人</th>
                  <th>创建时间</th>
                  <th>修改时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="knowledgeBase in pagedKnowledgeBases" :key="knowledgeBase.id">
                  <td>
                    <button class="link-btn" type="button" @click="openDocuments(knowledgeBase.id)">
                      {{ knowledgeBase.name }}
                    </button>
                  </td>
                  <td>{{ knowledgeBase.embedding_model }}</td>
                  <td><span class="badge">{{ knowledgeBase.collection_name || knowledgeBase.id }}</span></td>
                  <td>{{ knowledgeBase.document_count }}</td>
                  <td>{{ knowledgeBase.owner || "admin" }}</td>
                  <td>{{ formatDate(knowledgeBase.created_at) }}</td>
                  <td>{{ formatDate(knowledgeBase.updated_at || knowledgeBase.created_at) }}</td>
                  <td class="row-actions">
                    <button class="ghost-btn compact" type="button" @click="openDocuments(knowledgeBase.id)">文档</button>
                    <button class="ghost-btn compact" type="button" @click="openKnowledgeBaseEditModal(knowledgeBase.id)">修改</button>
                    <button
                      v-if="canManageKnowledge"
                      class="danger-btn compact"
                      type="button"
                      @click="removeKnowledgeBase(knowledgeBase.id)"
                    >
                      删除
                    </button>
                  </td>
                </tr>
                <tr v-if="!loading && filteredKnowledgeBases.length === 0">
                  <td colspan="8" class="empty-cell">暂无知识库，先新建一个。</td>
                </tr>
              </tbody>
            </table>
            </div>
            <div class="table-pagination">
              <span>{{ paginationLabel(filteredKnowledgeBases.length, knowledgeBasePage) }}</span>
              <div>
                <button class="ghost-btn compact" type="button" :disabled="knowledgeBasePage <= 1" @click="knowledgeBasePage = previousPage(knowledgeBasePage)">上一页</button>
                <button class="ghost-btn compact" type="button" :disabled="knowledgeBasePage >= totalPages(filteredKnowledgeBases.length)" @click="knowledgeBasePage = nextPage(knowledgeBasePage, filteredKnowledgeBases.length)">下一页</button>
              </div>
            </div>
          </section>

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

            <section class="table-card">
              <div class="table-toolbar">
                <div>
                  <h2>文档列表</h2>
                  <p>上传后会解析为可预览文档，点击“切块”后再生成分块和向量索引。</p>
                </div>
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
              </div>

              <div class="table-scroll">
              <table class="data-table document-table">
                <thead>
                  <tr>
                    <th>文档</th>
                    <th>来源</th>
                    <th>处理模式</th>
                    <th>状态</th>
                    <th>分块数</th>
                    <th>类型</th>
                    <th>大小</th>
                    <th>更新时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="document in pagedDocuments" :key="document.id">
                    <td>
                      <button
                        class="link-btn"
                        type="button"
                        :disabled="document.vector_chunk_count <= 0"
                        @click="openChunks(document.id)"
                      >
                        {{ document.title }}
                      </button>
                    </td>
                    <td>{{ sourceLabel(document.source_type) }}</td>
                    <td>{{ processingModeLabel(document.processing_mode) }}</td>
                    <td>
                      <span class="status-pill" :class="statusClass(reindexingDocumentId === document.id ? 'indexing' : document.vector_index_status)">
                        {{ statusLabel(reindexingDocumentId === document.id ? 'indexing' : document.vector_index_status) }}
                      </span>
                    </td>
                    <td>{{ document.vector_chunk_count }}</td>
                    <td>{{ documentTypeLabel(document.document_type) }}</td>
                    <td>{{ document.size_label }}</td>
                    <td>{{ formatDate(document.vector_indexed_at || document.created_at) }}</td>
                    <td class="row-actions">
                      <button class="ghost-btn compact" type="button" @click="openDocumentPreview(document.id)">
                        预览
                      </button>
                      <button
                        class="ghost-btn compact"
                        type="button"
                        :disabled="document.vector_chunk_count <= 0"
                        @click="openChunks(document.id)"
                      >
                        分块详情
                      </button>
                      <button class="ghost-btn compact" type="button" @click="openDocumentEditModal(document.id)">修改</button>
                      <button
                        v-if="canManageKnowledge"
                        class="ghost-btn compact"
                        type="button"
                        :disabled="reindexingDocumentId === document.id || document.vector_index_status === 'indexed'"
                        @click="runChunking(document.id)"
                      >
                        {{ reindexingDocumentId === document.id ? "切块中..." : "切块" }}
                      </button>
                      <button
                        v-if="canManageKnowledge"
                        class="danger-btn compact"
                        type="button"
                        @click="removeDocument(document.id)"
                      >
                        删除
                      </button>
                    </td>
                  </tr>
                  <tr v-if="!documentLoading && filteredDocuments.length === 0">
                    <td colspan="9" class="empty-cell">暂无文档，请上传文档。</td>
                  </tr>
                </tbody>
              </table>
              </div>
              <div class="table-pagination">
                <span>{{ paginationLabel(filteredDocuments.length, documentPage) }}</span>
                <div>
                  <button class="ghost-btn compact" type="button" :disabled="documentPage <= 1" @click="documentPage = previousPage(documentPage)">上一页</button>
                  <button class="ghost-btn compact" type="button" :disabled="documentPage >= totalPages(filteredDocuments.length)" @click="documentPage = nextPage(documentPage, filteredDocuments.length)">下一页</button>
                </div>
              </div>
            </section>
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

            <section class="table-card">
              <div class="table-toolbar">
                <div>
                  <h2>Chunk 列表</h2>
                  <p>展示当前文档真实入库的切块内容与元数据。</p>
                </div>
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
              </div>

              <div class="table-scroll">
              <table class="data-table chunk-table">
                <thead>
                  <tr>
                    <th class="select-col">
                      <input :checked="allVisibleChunksSelected" type="checkbox" @change="toggleVisibleChunkSelection" />
                    </th>
                    <th>序号</th>
                    <th>内容</th>
                    <th>状态</th>
                    <th>字符数</th>
                    <th>策略</th>
                    <th>元数据</th>
                    <th>更新时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="chunk in pagedChunks" :key="chunk.id">
                    <td class="select-col">
                      <input v-model="selectedChunkIds" :value="chunk.id" type="checkbox" />
                    </td>
                    <td>{{ chunk.chunk_index }}</td>
                    <td class="chunk-content"><span class="chunk-content-preview">{{ chunk.content }}</span></td>
                    <td>
                      <span class="status-pill" :class="{ success: chunk.enabled, warning: !chunk.enabled }">
                        {{ chunk.enabled ? "启用" : "禁用" }}
                      </span>
                    </td>
                    <td>{{ chunk.char_count }}</td>
                    <td>{{ chunk.strategy }}</td>
                    <td>{{ chunkMetadataSummary(chunk.metadata) }}</td>
                    <td>{{ formatDate(chunk.created_at) }}</td>
                    <td class="row-actions">
                      <button class="ghost-btn compact" type="button" @click="openChunkEditModal(chunk.id)">修改</button>
                      <button class="ghost-btn compact" type="button" @click="setChunkEnabled(chunk.id, !chunk.enabled)">
                        {{ chunk.enabled ? "禁用" : "启用" }}
                      </button>
                      <button class="danger-btn compact" type="button" @click="removeChunk(chunk.id)">删除</button>
                    </td>
                  </tr>
                  <tr v-if="!chunkLoading && filteredChunks.length === 0">
                    <td colspan="9" class="empty-cell">暂无切块，请先在文档管理中开启切块。</td>
                  </tr>
                </tbody>
              </table>
              </div>
              <div class="table-pagination">
                <span>{{ paginationLabel(filteredChunks.length, chunkPage) }}</span>
                <div>
                  <button class="ghost-btn compact" type="button" :disabled="chunkPage <= 1" @click="chunkPage = previousPage(chunkPage)">上一页</button>
                  <button class="ghost-btn compact" type="button" :disabled="chunkPage >= totalPages(filteredChunks.length)" @click="chunkPage = nextPage(chunkPage, filteredChunks.length)">下一页</button>
                </div>
              </div>
            </section>
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
          <div class="page-head">
            <div>
              <h1>意图管理</h1>
              <p>维护意图树、意图列表和节点路由配置，数据持久化在后台 admin_intent_nodes 表。</p>
            </div>
            <div class="page-actions">
              <div class="segmented-tabs">
                <button :class="{ active: intentMode === 'tree' }" type="button" @click="intentMode = 'tree'">意图树配置</button>
                <button :class="{ active: intentMode === 'list' }" type="button" @click="intentMode = 'list'">意图列表</button>
              </div>
              <button class="ghost-btn" type="button" @click="void refreshKnowledgeData()">刷新</button>
              <button class="primary-btn" type="button" @click="openIntentModal">新建意图节点</button>
            </div>
          </div>

          <section v-if="intentMode === 'tree'" class="admin-grid-two">
            <article class="task-card intent-tree-panel">
              <div class="table-toolbar">
                <div>
                  <h2>意图树配置</h2>
                  <p>点击节点查看详情，支持新增子节点、编辑与删除。</p>
                </div>
              </div>
              <div class="intent-tree-box real-tree">
                <div v-for="node in rootIntentNodes" :key="node.id" class="intent-tree-group">
                  <button
                    class="intent-node root-node tree-button"
                    :class="{ active: selectedIntentNode?.id === node.id }"
                    type="button"
                    @click="selectedIntentNodeId = node.id"
                  >
                    <strong>{{ node.name }}</strong>
                    <span class="intent-tag-row">
                      <i class="intent-tag" :class="intentNodeLevelClass(node.level)">{{ node.level }}</i>
                      <i class="intent-tag" :class="intentNodeTypeClass(node.node_type)">{{ node.node_type }}</i>
                      <i class="intent-tag" :class="{ disabled: !node.enabled }">{{ node.enabled ? "启用" : "停用" }}</i>
                    </span>
                  </button>
                  <div v-if="childIntentNodes(node.id).length > 0" class="intent-child-list">
                    <button
                      v-for="child in childIntentNodes(node.id)"
                      :key="child.id"
                      class="intent-node child-node tree-button"
                      :class="{ active: selectedIntentNode?.id === child.id }"
                      type="button"
                      @click="selectedIntentNodeId = child.id"
                    >
                      <strong>{{ child.name }}</strong>
                      <span class="intent-tag-row">
                        <i class="intent-tag" :class="intentNodeLevelClass(child.level)">{{ child.level }}</i>
                        <i class="intent-tag" :class="intentNodeTypeClass(child.node_type)">{{ child.node_type }}</i>
                        <i class="intent-parent-label">{{ node.name }}</i>
                      </span>
                    </button>
                  </div>
                </div>
                <div v-if="adminIntentNodes.length === 0" class="empty-cell">暂无意图节点，请点击右上角新建。</div>
              </div>
            </article>

            <article class="task-card intent-detail-card">
              <template v-if="selectedIntentNode">
                <div class="intent-detail-head">
                  <div>
                    <h2>{{ selectedIntentNode.name }}</h2>
                    <div class="intent-detail-meta">
                      <span>{{ selectedIntentNode.code }}</span>
                      <i class="intent-tag" :class="intentNodeLevelClass(selectedIntentNode.level)">{{ selectedIntentNode.level }}</i>
                      <i class="intent-tag" :class="intentNodeTypeClass(selectedIntentNode.node_type)">{{ selectedIntentNode.node_type }}</i>
                    </div>
                  </div>
                  <span class="status-pill" :class="{ success: selectedIntentNode.enabled, warning: !selectedIntentNode.enabled }">
                    {{ selectedIntentNode.enabled ? "启用" : "停用" }}
                  </span>
                </div>
                <dl class="setting-list">
                  <dt>父节点</dt>
                  <dd>{{ selectedIntentNode.parent_id }}</dd>
                  <dt>知识库</dt>
                  <dd>{{ selectedIntentNode.knowledge_base_id || "-" }}</dd>
                  <dt>Collection</dt>
                  <dd>{{ selectedIntentNode.collection_name || "-" }}</dd>
                  <dt>TopK / 排序</dt>
                  <dd>{{ selectedIntentNode.top_k ?? "默认" }} / {{ selectedIntentNode.sort_order }}</dd>
                  <dt>描述</dt>
                  <dd>{{ selectedIntentNode.description || "-" }}</dd>
                  <dt>规则片段</dt>
                  <dd>{{ selectedIntentNode.rule_snippet || "-" }}</dd>
                </dl>
                <div class="tag-row">
                  <span v-for="question in selectedIntentNode.sample_questions" :key="question" class="soft-tag">{{ question }}</span>
                  <span v-if="selectedIntentNode.sample_questions.length === 0" class="muted-line">暂无示例问题</span>
                </div>
                <div class="page-actions section-gap">
                  <button class="ghost-btn" type="button" @click="openIntentChildModal(selectedIntentNode.id)">新增子节点</button>
                  <button class="ghost-btn" type="button" @click="openIntentEditModal(selectedIntentNode.id)">编辑节点</button>
                  <button class="danger-btn" type="button" @click="void deleteIntentNodeFromInput(selectedIntentNode.id)">删除节点</button>
                </div>
              </template>
              <div v-else class="empty-cell">请选择一个意图节点。</div>
            </article>
          </section>

          <section v-else class="table-card section-gap">
            <div class="table-toolbar">
              <div>
                <h2>意图列表</h2>
                <p>按节点名称、编码或 ID 搜索；点击“定位树”可跳转到意图树对应节点。</p>
              </div>
              <div class="toolbar-actions">
                <input v-model="intentSearch" class="ui-input" type="text" placeholder="搜索意图名称 / Code / ID" />
                <button class="ghost-btn" type="button" @click="intentSearch = ''">清空筛选</button>
              </div>
            </div>
            <div class="table-scroll">
              <table class="data-table intent-table">
                <thead>
                  <tr>
                    <th>意图节点</th>
                    <th>层级</th>
                    <th>类型</th>
                    <th>路径</th>
                    <th>关联资源</th>
                    <th>示例数</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in pagedRealIntentRows" :key="item.id">
                    <td><strong>{{ item.name }}</strong><p class="muted-line">{{ item.code }} · {{ item.id }}</p></td>
                    <td><span class="badge">{{ item.level }}</span></td>
                    <td>{{ item.type }}</td>
                    <td>{{ item.path }}</td>
                    <td>{{ item.resource }}</td>
                    <td>{{ item.sampleCount }}</td>
                    <td><span class="status-pill" :class="{ success: item.enabled, warning: !item.enabled }">{{ item.status }}</span></td>
                    <td class="table-actions-cell">
                      <button class="ghost-btn compact" type="button" @click="locateIntentNode(item.id)">定位树</button>
                      <button class="ghost-btn compact" type="button" @click="openIntentEditModal(item.id)">修改</button>
                    </td>
                  </tr>
                  <tr v-if="realIntentRows.length === 0">
                    <td colspan="8" class="empty-cell">暂无意图节点。</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="table-pagination">
              <span>{{ paginationLabel(realIntentRows.length, realIntentPage) }}</span>
              <div>
                <button class="ghost-btn compact" type="button" :disabled="realIntentPage <= 1" @click="realIntentPage = previousPage(realIntentPage)">上一页</button>
                <button class="ghost-btn compact" type="button" :disabled="realIntentPage >= totalPages(realIntentRows.length)" @click="realIntentPage = nextPage(realIntentPage, realIntentRows.length)">下一页</button>
              </div>
            </div>
          </section>
        </template>

        <template v-else-if="false">
          <div class="page-head">
            <div>
              <h1>意图树配置</h1>
              <p>配置意图层级、类型和节点关系。</p>
            </div>
            <div class="page-actions">
              <button class="ghost-btn" type="button" @click="void refreshKnowledgeData()">刷新</button>
              <button class="ghost-btn" type="button" @click="openIntentModal">新建意图节点</button>
              <button class="primary-btn" type="button" :disabled="routeProfileLoading || !routeProfile" @click="saveRouteProfile">
                保存意图配置
              </button>
            </div>
          </div>

          <section class="admin-grid-two">
            <article class="task-card">
              <h2>意图树结构</h2>
              <p>点击节点查看详情或进行编辑。</p>
              <div class="intent-tree-box">
                <div class="intent-node root-node">
                  <strong>{{ selectedKnowledgeBase?.name || "未选择知识库" }}</strong>
                  <span>DOMAIN · KB</span>
                </div>
                <div v-for="question in routeProfile?.sample_questions || []" :key="question" class="intent-node child-node">
                  <strong>{{ question }}</strong>
                  <span>CATEGORY · 示例问题</span>
                </div>
              </div>
            </article>

            <article class="task-card">
              <h2>节点详情</h2>
              <p>当前知识库：{{ selectedKnowledgeBase?.name || "-" }}</p>
              <textarea
                v-if="routeProfile"
                v-model="routeProfile.profile_text"
                class="ui-input profile-textarea"
                placeholder="描述这个知识库适合回答的问题、业务范围和命中条件。"
              ></textarea>
            </article>
          </section>

          <section class="table-card section-gap">
            <div class="table-toolbar">
              <div>
                <h2>意图列表</h2>
                <p>支持搜索并快速定位当前知识库的意图节点。</p>
              </div>
              <div class="toolbar-actions">
                <input v-model="intentSearch" class="ui-input" type="text" placeholder="搜索意图名称/ID" />
                <button class="ghost-btn" type="button">清空筛选</button>
              </div>
            </div>
            <div class="table-scroll">
              <table class="data-table intent-table">
                <thead>
                  <tr>
                    <th>意图节点</th>
                    <th>层级</th>
                    <th>类型</th>
                    <th>路径</th>
                    <th>关联资源</th>
                    <th>示例数</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in intentRows" :key="item.id">
                    <td><strong>{{ item.name }}</strong><p class="muted-line">{{ item.id }}</p></td>
                    <td><span class="badge">{{ item.level }}</span></td>
                    <td>{{ item.type }}</td>
                    <td>{{ item.path }}</td>
                    <td>{{ item.resource }}</td>
                    <td>{{ item.sampleCount }}</td>
                    <td><span class="status-pill success">{{ item.status }}</span></td>
                    <td><button class="ghost-btn compact" type="button">定位到意图树</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </template>

        <template v-else-if="currentTab === 'keyword'">
          <div class="page-head">
            <div>
              <h1>关键词映射</h1>
              <p>维护知识库命中的关键词，和意图识别共同决定检索范围。</p>
            </div>
            <button class="primary-btn" type="button" :disabled="routeProfileLoading || !routeProfile" @click="saveRouteProfile">
              保存关键词
            </button>
          </div>

          <section class="table-card">
            <div class="table-toolbar">
              <div>
                <h2>关键词映射管理</h2>
                <p>配置查询归一化的关键词映射规则。</p>
              </div>
              <div class="toolbar-actions">
                <input v-model="keywordSearch" class="ui-input" type="text" placeholder="搜索原始词/目标词" />
                <button class="ghost-btn" type="button" @click="openKeywordModal">新增映射</button>
              </div>
            </div>
            <div v-if="false" class="inline-form mapping-form">
              <input v-model="newKeyword" class="ui-input" type="text" placeholder="输入原始词，如 RAG、退货政策、保险理赔" />
              <button class="primary-btn" type="button" @click="addKeywordFromInput">添加关键词</button>
            </div>
            <div class="table-scroll">
              <table class="data-table mapping-table">
                <thead>
                  <tr>
                    <th>原始词</th>
                    <th>目标词</th>
                    <th>匹配类型</th>
                    <th>优先级</th>
                    <th>状态</th>
                    <th>备注</th>
                    <th>更新时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in pagedRealKeywordRows" :key="item.id">
                    <td>{{ item.raw }}</td>
                    <td>{{ item.target }}</td>
                    <td>{{ item.matchType }}</td>
                    <td>{{ item.priority }}</td>
                    <td><span class="status-pill" :class="{ success: item.enabled, warning: !item.enabled }">{{ item.status }}</span></td>
                    <td>{{ item.remark }}</td>
                    <td>{{ formatDate(item.updatedAt) }}</td>
                    <td class="table-actions-cell">
                      <button class="ghost-btn compact" type="button" @click="openKeywordEditModal(item.id)">修改</button>
                      <button class="danger-btn compact" type="button" @click="removeKeywordByValue(item.id)">删除</button>
                    </td>
                  </tr>
                  <tr v-if="realKeywordRows.length === 0">
                    <td colspan="8" class="empty-cell">暂无关键词映射。</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="table-pagination">
              <span>{{ paginationLabel(realKeywordRows.length, keywordPage) }}</span>
              <div>
                <button class="ghost-btn compact" type="button" :disabled="keywordPage <= 1" @click="keywordPage = previousPage(keywordPage)">上一页</button>
                <button class="ghost-btn compact" type="button" :disabled="keywordPage >= totalPages(realKeywordRows.length)" @click="keywordPage = nextPage(keywordPage, realKeywordRows.length)">下一页</button>
              </div>
            </div>
          </section>
        </template>

        <template v-else-if="currentTab === 'pipeline'">
          <div class="page-head">
            <div>
              <h1>数据通道</h1>
              <p>{{ pipelineTab === "pipelines" ? "配置节点顺序与处理逻辑。" : "监控流水线任务执行状态。" }}</p>
            </div>
          </div>

          <section v-if="pipelineTab === 'pipelines'" class="table-card">
            <div class="table-toolbar">
              <div>
                <h2>通道流水线</h2>
                <p>配置节点顺序与处理逻辑。</p>
              </div>
              <div class="toolbar-actions">
                <input v-model="pipelineSearch" class="ui-input toolbar-input" type="text" placeholder="搜索流水线名称" />
                <button class="ghost-btn" type="button" @click="pipelinePage = 1">搜索</button>
                <button class="ghost-btn" type="button" @click="void refreshKnowledgeData()">刷新</button>
                <button class="primary-btn" type="button" @click="openCreatePipelineModal">新建流水线</button>
              </div>
            </div>
            <div class="table-scroll">
              <table class="data-table pipeline-table">
                <thead>
                  <tr>
                    <th>名称</th>
                    <th>描述</th>
                    <th>节点数</th>
                    <th>负责人</th>
                    <th>任务数</th>
                    <th>更新时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="pipeline in pagedPipelineRows" :key="pipeline.id">
                    <td><strong>{{ pipeline.name }}</strong></td>
                    <td class="wide-cell">{{ pipeline.description }}</td>
                    <td>{{ pipeline.nodeCount }}</td>
                    <td>{{ pipeline.owner }}</td>
                    <td>{{ pipeline.taskCount }}</td>
                    <td>{{ formatDate(pipeline.updatedAt) }}</td>
                    <td class="row-actions">
                      <button class="ghost-btn compact" type="button" @click="openPipelineNodesModal(pipeline)">查看节点</button>
                      <button class="ghost-btn compact" type="button" @click="openEditPipelineModal(pipeline)">修改</button>
                      <button class="danger-btn compact" type="button" @click="void deletePipelineFromRow(pipeline.id)">删除</button>
                    </td>
                  </tr>
                  <tr v-if="pipelineRows.length === 0">
                    <td colspan="7" class="empty-cell">暂无流水线，请点击“新增流水线”创建。</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="table-pagination">
              <span>{{ paginationLabel(pipelineRows.length, pipelinePage) }}</span>
              <div>
                <button class="ghost-btn compact" type="button" :disabled="pipelinePage <= 1" @click="pipelinePage = previousPage(pipelinePage)">上一页</button>
                <button class="ghost-btn compact" type="button" :disabled="pipelinePage >= totalPages(pipelineRows.length)" @click="pipelinePage = nextPage(pipelinePage, pipelineRows.length)">下一页</button>
              </div>
            </div>
          </section>

          <section v-else class="table-card">
              <div class="table-toolbar">
                <div>
                  <h2>通道任务</h2>
                  <p>监控执行状态，共 {{ filteredIngestionTasks.length }} 条任务。</p>
                </div>
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
              </div>
              <div class="table-scroll">
                <table class="data-table pipeline-table pipeline-task-table">
                  <thead>
                    <tr>
                      <th>任务 ID</th>
                      <th>知识库</th>
                      <th>文档</th>
                      <th>来源</th>
                      <th>状态</th>
                      <th>分块数</th>
                      <th>创建时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="task in pagedIngestionTasks" :key="task.id">
                      <td>#{{ task.id }}</td>
                      <td>{{ task.knowledge_base_id }}</td>
                      <td>{{ task.document_id }}</td>
                      <td>{{ sourceLabel(task.source_type) }}</td>
                      <td>
                        <span class="status-pill" :class="{ success: task.status === 'completed', danger: task.status === 'failed', warning: task.status !== 'completed' && task.status !== 'failed' }">
                          {{ task.status }}
                        </span>
                      </td>
                      <td>{{ task.chunk_count }}</td>
                      <td>{{ formatDate(task.created_at) }}</td>
                    </tr>
                    <tr v-if="filteredIngestionTasks.length === 0">
                      <td colspan="7" class="empty-cell">暂无流水线任务。</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="table-pagination">
                <span>{{ paginationLabel(filteredIngestionTasks.length, ingestionTaskPage) }}</span>
                <div>
                  <button class="ghost-btn compact" type="button" :disabled="ingestionTaskPage <= 1" @click="ingestionTaskPage = previousPage(ingestionTaskPage)">上一页</button>
                  <button class="ghost-btn compact" type="button" :disabled="ingestionTaskPage >= totalPages(filteredIngestionTasks.length)" @click="ingestionTaskPage = nextPage(ingestionTaskPage, filteredIngestionTasks.length)">下一页</button>
                </div>
              </div>
          </section>
        </template>

        <template v-else-if="currentTab === 'trace'">
          <template v-if="!selectedAdminTrace">
            <div class="page-head">
              <div>
                <h1>链路追踪</h1>
                <p>按 TraceID 检索运行记录，点击查看链路详情。</p>
              </div>
              <div class="page-actions">
                <input v-model="adminTraceId" class="ui-input" inputmode="numeric" maxlength="20" type="text" placeholder="输入 20 位 TraceID" />
                <button class="ghost-btn" type="button" @click="void searchAdminTraces()">搜索</button>
                <button class="ghost-btn" type="button" @click="void loadAdminTraces(adminTracePage)">刷新</button>
              </div>
            </div>

            <section class="table-card">
              <div class="table-scroll">
                <table class="data-table trace-table">
                  <thead>
                    <tr>
                      <th>Trace Name</th>
                      <th>Trace Id</th>
                      <th>会话ID / TaskID</th>
                      <th>用户名</th>
                      <th>耗时</th>
                      <th>状态</th>
                      <th>执行时间</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="trace in pagedTraceRows" :key="trace.id">
                      <td><strong>{{ trace.name }}</strong><p class="muted-line">{{ trace.title }}</p></td>
                      <td>{{ trace.traceId }}</td>
                      <td>{{ trace.id }} / {{ trace.latestMessageId }}</td>
                      <td>{{ trace.owner }}</td>
                      <td>{{ trace.duration }}</td>
                      <td><span class="status-pill" :class="{ success: trace.status === 'SUCCESS', warning: trace.status !== 'SUCCESS' }">{{ trace.status }}</span></td>
                      <td>{{ formatDate(trace.executedAt) }}</td>
                      <td><button class="ghost-btn compact" type="button" @click="loadTraceDetail(trace.id)">查看链路</button></td>
                    </tr>
                    <tr v-if="traceRows.length === 0">
                      <td colspan="8" class="empty-cell">暂无链路数据，开始聊天后这里会展示会话与消息链路。</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="table-pagination">
                <span>第 {{ adminTracePage }} / {{ Math.max(1, Math.ceil(adminTraceTotal / adminTracePageSize)) }} 页，共 {{ adminTraceTotal }} 条</span>
                <div>
                  <button class="ghost-btn compact" type="button" :disabled="adminTracePage <= 1" @click="void loadAdminTraces(adminTracePage - 1)">上一页</button>
                  <button class="ghost-btn compact" type="button" :disabled="adminTracePage >= Math.max(1, Math.ceil(adminTraceTotal / adminTracePageSize))" @click="void loadAdminTraces(adminTracePage + 1)">下一页</button>
                </div>
              </div>
            </section>
          </template>

          <template v-else>
            <div class="page-head trace-detail-head">
              <div>
                <p class="muted-line">RAG 链路列表 / 链路详情</p>
                <h1>rag-stream-chat <span class="status-pill success">SUCCESS</span></h1>
                <p># {{ selectedAdminTrace.id }} · {{ formatDate(selectedAdminTrace.latest_message_at) }} · {{ selectedAdminTrace.owner_username || selectedAdminTrace.owner_id || "unknown" }}</p>
              </div>
              <div class="page-actions">
                <button class="ghost-btn" type="button" @click="clearTraceDetail">返回列表</button>
                <button class="ghost-btn" type="button" @click="loadTraceDetail(selectedAdminTrace.id)">刷新</button>
              </div>
            </div>

            <section class="trace-summary-strip">
              <article><span>节点</span><strong>{{ selectedTraceStats.nodeCount }}</strong></article>
              <article><span>成功</span><strong>{{ selectedTraceStats.successCount }}</strong></article>
              <article><span>失败</span><strong>{{ selectedTraceStats.failedCount }}</strong></article>
              <article><span>用户消息</span><strong>{{ selectedTraceStats.userMessages }}</strong></article>
              <article><span>助手回复</span><strong>{{ selectedTraceStats.assistantMessages }}</strong></article>
            </section>

            <section class="trace-detail-grid">
              <article class="table-card trace-timeline-card">
                <div class="table-toolbar">
                  <div>
                    <h2>执行时序</h2>
                    <p>当前基于会话消息构建链路视图；后续可接入 LangSmith/节点耗时后替换为真实执行耗时。</p>
                  </div>
                </div>
                <div class="trace-timeline">
                  <div class="trace-axis">
                    <span>开始</span>
                    <span>检索 / 工具</span>
                    <span>生成</span>
                    <span>完成</span>
                  </div>
                  <div v-for="node in selectedTraceRows" :key="node.id" class="trace-node-row">
                    <div class="trace-node-name">
                      <span class="trace-dot"></span>
                      <strong>{{ node.name }}</strong>
                      <small>{{ node.type }}</small>
                    </div>
                    <div class="trace-bar-track">
                      <span class="trace-bar" :style="{ left: `${node.offset}%`, width: `${node.width}%` }"></span>
                    </div>
                    <div class="trace-node-duration">
                      <strong>{{ node.duration }}</strong>
                      <small>{{ formatDate(node.startedAt) }}</small>
                    </div>
                  </div>
                </div>
              </article>

            </section>

            <section class="table-card section-gap">
              <div class="table-toolbar">
                <div>
                  <h2>消息链路</h2>
                  <p>展示本次会话中的用户输入与助手输出摘要。</p>
                </div>
              </div>
              <div class="trace-message-list">
                <article v-for="message in selectedAdminTrace.messages" :key="message.id" class="trace-message-item" :class="message.role">
                  <span class="status-pill">{{ message.role }}</span>
                  <div>
                    <strong>#{{ message.id }} · {{ formatDate(message.created_at) }}</strong>
                    <p>{{ message.content_preview }}</p>
                  </div>
                </article>
              </div>
            </section>
          </template>
        </template>

        <template v-else-if="currentTab === 'users'">
          <div class="page-head">
            <div>
              <h1>用户管理</h1>
              <p>管理后台账号与角色权限。</p>
            </div>
            <div class="page-actions">
              <input v-model="userSearch" class="ui-input" type="text" placeholder="搜索用户名或角色" />
              <button class="ghost-btn" type="button" @click="void refreshKnowledgeData()">刷新</button>
              <button class="primary-btn" type="button" @click="openUserModal">新增用户</button>
            </div>
          </div>

          <section class="table-card">
            <div v-if="false" class="inline-form user-create-form">
              <input v-model="newAdminUsername" class="ui-input" type="text" placeholder="用户名，至少 3 位" />
              <input v-model="newAdminPassword" class="ui-input" type="password" placeholder="初始密码，至少 8 位" />
              <select v-model="newAdminRole" class="ui-input">
                <option value="user">user</option>
                <option value="admin">admin</option>
              </select>
              <button class="primary-btn" type="button" @click="createAdminUserFromInput">新增用户</button>
            </div>
            <div class="table-scroll">
              <table class="data-table user-table">
                <thead>
                  <tr>
                    <th>用户</th>
                    <th>角色</th>
                    <th>创建时间</th>
                    <th>更新时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="user in pagedAdminUsers" :key="user.id">
                    <td><strong>{{ user.username }}</strong><p class="muted-line">{{ user.id }}</p></td>
                    <td><span class="status-pill" :class="{ success: user.role === 'admin' }">{{ user.role }}</span></td>
                    <td>{{ formatDate(user.created_at) }}</td>
                    <td>{{ formatDate(user.created_at) }}</td>
                    <td class="row-actions">
                      <button class="ghost-btn compact" type="button" @click="openUserEditModal(user.id)">修改</button>
                      <button class="ghost-btn compact" type="button" :disabled="user.role === 'admin'" @click="changeUserRole(user.id, 'admin')">设置管理员</button>
                      <button class="ghost-btn compact" type="button" :disabled="user.role === 'user'" @click="changeUserRole(user.id, 'user')">设置普通用户</button>
                      <button class="danger-btn compact" type="button" @click="removeUser(user.id)">删除</button>
                    </td>
                  </tr>
                  <tr v-if="filteredAdminUsers.length === 0">
                    <td colspan="5" class="empty-cell">暂无匹配用户。</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="table-pagination">
              <span>{{ paginationLabel(filteredAdminUsers.length, userPage) }}</span>
              <div>
                <button class="ghost-btn compact" type="button" :disabled="userPage <= 1" @click="userPage = previousPage(userPage)">上一页</button>
                <button class="ghost-btn compact" type="button" :disabled="userPage >= totalPages(filteredAdminUsers.length)" @click="userPage = nextPage(userPage, filteredAdminUsers.length)">下一页</button>
              </div>
            </div>
          </section>
        </template>

        <template v-else-if="currentTab === 'sampleQuestions'">
          <div class="page-head">
            <div>
              <h1>示例问题管理</h1>
              <p>配置欢迎页的示例问题与推荐问法。</p>
            </div>
            <div class="page-actions">
              <input v-model="sampleQuestionSearch" class="ui-input" type="text" placeholder="搜索标题/描述/问题" />
              <button class="ghost-btn" type="button" @click="void loadSampleQuestions()">刷新</button>
              <button class="ghost-btn" type="button" @click="openSampleQuestionModal">新增示例问题</button>
            </div>
          </div>

          <section class="table-card">
            <div class="table-toolbar">
              <div>
                <h2>示例问题</h2>
                <p>用于聊天首页推荐问法展示。</p>
              </div>
            </div>
            <div v-if="false" class="inline-form mapping-form">
              <input v-model="newSampleQuestion" class="ui-input" type="text" placeholder="输入示例问题，如 RetriFlow 一期应该先做什么？" />
              <button class="primary-btn" type="button" @click="addSampleQuestionFromInput">新增示例</button>
            </div>
            <div class="table-scroll">
              <table class="data-table sample-table">
                <thead>
                  <tr>
                    <th>标题</th>
                    <th>描述</th>
                    <th>示例问题</th>
                    <th>更新时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in pagedSampleQuestionRows" :key="item.id">
                    <td>{{ item.title }}</td>
                    <td>{{ item.description }}</td>
                    <td class="wide-cell">{{ item.question }}</td>
                    <td>{{ formatDate(item.updatedAt) }}</td>
                    <td><button class="danger-btn compact" type="button" @click="removeSampleQuestionByValue(item.id)">删除</button></td>
                  </tr>
                  <tr v-if="sampleQuestionRows.length === 0">
                    <td colspan="5" class="empty-cell">暂无示例问题。</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="table-pagination">
              <span>{{ paginationLabel(sampleQuestionRows.length, sampleQuestionPage) }}</span>
              <div>
                <button class="ghost-btn compact" type="button" :disabled="sampleQuestionPage <= 1" @click="sampleQuestionPage = previousPage(sampleQuestionPage)">上一页</button>
                <button class="ghost-btn compact" type="button" :disabled="sampleQuestionPage >= totalPages(sampleQuestionRows.length)" @click="sampleQuestionPage = nextPage(sampleQuestionPage, sampleQuestionRows.length)">下一页</button>
              </div>
            </div>
          </section>
        </template>

        <template v-else-if="currentTab === 'settings'">
          <div class="page-head">
            <div>
              <h1>系统配置</h1>
              <p>只读展示当前 application 配置，敏感密钥不会在后台展示。</p>
            </div>
            <button class="ghost-btn" type="button" @click="void refreshKnowledgeData()">刷新</button>
          </div>

          <section class="settings-grid">
            <article v-for="card in settingCards" :key="card.title" class="task-card">
              <h2>{{ card.title }}</h2>
              <dl class="setting-list">
                <template v-for="item in card.items" :key="item.label">
                  <dt>{{ item.label }}</dt>
                  <dd>{{ item.value }}</dd>
                </template>
              </dl>
            </article>
          </section>
        </template>
      </section>
    </main>

    <div v-if="showPipelineModal" class="modal-backdrop" @click.self="closeCreatePipelineModal">
      <section class="admin-modal admin-modal-wide" aria-label="新建流水线">
        <header class="modal-head">
          <div>
            <h2>{{ editingPipelineId === null ? "新建流水线" : "修改流水线" }}</h2>
            <p>{{ editingPipelineId === null ? "配置文档摄取、解析、切块、向量化等节点顺序，保存后会进入 RetriFlow 后端流水线定义表。" : "调整流水线名称、描述和节点配置。" }}</p>
          </div>
          <button class="modal-close" type="button" aria-label="关闭" @click="closeCreatePipelineModal">×</button>
        </header>

        <div class="modal-form">
          <label class="modal-label">
            流水线名称
            <input v-model="newPipelineName" class="ui-input" type="text" placeholder="例如 retriflow-custom-ingestion" />
          </label>
          <label class="modal-label wide">
            描述
            <textarea v-model="newPipelineDescription" class="ui-input" rows="3" placeholder="说明这条流水线负责什么场景"></textarea>
          </label>
        </div>

        <section class="pipeline-node-panel">
          <div class="node-panel-head">
            <div>
              <h3>节点配置</h3>
              <p>表单模式适合快速配置，JSON 模式适合复制已有流水线或批量调整。</p>
            </div>
            <div class="segmented-tabs">
              <button :class="{ active: pipelineEditorMode === 'form' }" type="button" @click="syncPipelineFormFromJson">表单配置</button>
              <button :class="{ active: pipelineEditorMode === 'json' }" type="button" @click="syncPipelineJsonFromForm">JSON 配置</button>
            </div>
          </div>

          <template v-if="pipelineEditorMode === 'form'">
            <div v-if="pipelineNodeDrafts.length === 0" class="empty-node-box">
              暂无节点，点击“添加节点”开始配置。
            </div>
            <article v-for="(node, index) in pipelineNodeDrafts" :key="`${node.node_id}-${index}`" class="pipeline-node-card">
              <div class="node-card-head">
                <div>
                  <span class="status-pill">{{ node.node_type }}</span>
                  <strong>节点 {{ index + 1 }}</strong>
                </div>
                <button class="danger-btn compact" type="button" @click="removePipelineNode(index)">删除</button>
              </div>
              <div class="pipeline-node-grid">
                <label class="modal-label">
                  节点 ID
                  <input v-model="node.node_id" class="ui-input" type="text" placeholder="parse" />
                </label>
                <label class="modal-label">
                  节点类型
                  <select v-model="node.node_type" class="ui-input">
                    <option v-for="type in pipelineNodeTypeOptions" :key="type" :value="type">{{ type }}</option>
                  </select>
                </label>
                <label class="modal-label">
                  下一节点 ID
                  <input v-model="node.next_node_id" class="ui-input" type="text" placeholder="chunk，可为空" />
                </label>
                <label class="modal-label">
                  条件
                  <input v-model="node.condition" class="ui-input" type="text" placeholder="例如 mime == application/pdf" />
                </label>
                <label class="modal-label wide">
                  节点配置 JSON
                  <textarea
                    class="ui-input pipeline-json-mini"
                    rows="4"
                    :value="JSON.stringify(node.config, null, 2)"
                    @input="updatePipelineNodeConfigFromEvent(index, $event)"
                  ></textarea>
                </label>
              </div>
            </article>
            <button class="ghost-btn" type="button" @click="addPipelineNode">添加节点</button>
          </template>

          <template v-else>
            <textarea v-model="pipelineJsonText" class="ui-input pipeline-json-textarea" spellcheck="false"></textarea>
          </template>
        </section>

        <footer class="modal-actions">
          <button class="ghost-btn" type="button" @click="closeCreatePipelineModal">取消</button>
          <button class="primary-btn" type="button" :disabled="!newPipelineName.trim()" @click="void savePipelineFromModal()">{{ editingPipelineId === null ? "保存流水线" : "保存修改" }}</button>
        </footer>
      </section>
    </div>

    <div v-if="activeAdminModal" class="modal-backdrop" @click.self="closeAdminModal">
      <section v-if="activeAdminModal === 'documentPreview'" class="admin-modal admin-modal-tall" aria-label="文档预览">
        <header class="modal-head">
          <div>
            <h2>{{ documentPreview?.title || "文档预览" }}</h2>
            <p>{{ documentPreview?.source_uri || "正在加载文档内容" }}</p>
          </div>
          <button class="modal-close" type="button" aria-label="关闭" @click="closeAdminModal">×</button>
        </header>
        <div class="document-preview-box">
          <p v-if="documentPreviewLoading" class="empty-cell">正在加载预览...</p>
          <pre v-else>{{ documentPreview?.content || "暂无可预览内容" }}</pre>
        </div>
        <footer class="modal-actions">
          <button class="ghost-btn" type="button" @click="closeAdminModal">关闭</button>
        </footer>
      </section>

      <section v-else-if="activeAdminModal === 'pipelineNodes'" class="admin-modal admin-modal-wide" aria-label="查看流水线节点">
        <header class="modal-head">
          <div>
            <h2>查看节点</h2>
            <p>{{ selectedPipelineName }}，共 {{ selectedPipelineNodes.length }} 个节点。</p>
          </div>
          <button class="modal-close" type="button" aria-label="关闭" @click="closeAdminModal">×</button>
        </header>
        <section class="pipeline-node-panel readonly-node-panel">
          <article v-for="(node, index) in selectedPipelineNodes" :key="`${node.node_id}-${index}`" class="pipeline-node-card">
            <div class="node-card-head">
              <div>
                <span class="status-pill">{{ node.node_type }}</span>
                <strong>{{ index + 1 }}. {{ node.node_id }}</strong>
              </div>
              <span class="muted-line">next: {{ node.next_node_id || "-" }}</span>
            </div>
            <dl class="node-detail-list">
              <dt>条件</dt>
              <dd>{{ node.condition || "-" }}</dd>
              <dt>配置</dt>
              <dd><pre>{{ JSON.stringify(node.config || {}, null, 2) }}</pre></dd>
            </dl>
          </article>
          <p v-if="selectedPipelineNodes.length === 0" class="empty-cell">暂无节点。</p>
        </section>
        <footer class="modal-actions">
          <button class="ghost-btn" type="button" @click="closeAdminModal">关闭</button>
        </footer>
      </section>

      <section v-else-if="activeAdminModal === 'knowledgeBase'" class="admin-modal" aria-label="创建知识库">
        <header class="modal-head">
          <div>
            <h2>{{ editingKnowledgeBaseId ? "修改知识库" : "创建知识库" }}</h2>
            <p>{{ editingKnowledgeBaseId ? "更新知识库名称、模型和 collection 配置。" : "创建一个新的知识库，用于存储和检索文档。" }}</p>
          </div>
          <button class="modal-close" type="button" aria-label="关闭" @click="closeAdminModal">×</button>
        </header>
        <div class="modal-form single">
          <label class="modal-label">
            知识库名称
            <input v-model="newKnowledgeBaseName" class="ui-input modal-control" type="text" placeholder="例如：产品文档库" />
            <span>为知识库起一个易于识别的名称。</span>
          </label>
          <label class="modal-label">
            Embedding 模型
            <select v-model="newKnowledgeEmbeddingModel" class="ui-input modal-control">
              <option v-for="model in knowledgeEmbeddingModelOptions" :key="model.value" :value="model.value">{{ model.label }}</option>
            </select>
            <span>当前后端按全局配置入库，这里作为创建时的展示配置。</span>
          </label>
          <label class="modal-label">
            Collection 名称
            <input v-model="newKnowledgeCollectionName" class="ui-input modal-control" type="text" placeholder="例如：productdocs" />
            <span>当前后端会自动使用知识库 ID 作为 collection。</span>
          </label>
        </div>
        <footer class="modal-actions">
          <button class="ghost-btn" type="button" @click="closeAdminModal">取消</button>
          <button class="primary-btn" type="button" :disabled="!newKnowledgeBaseName.trim()" @click="void createKnowledgeBaseFromInput()">
            {{ editingKnowledgeBaseId ? "保存" : "创建" }}
          </button>
        </footer>
      </section>

      <section v-else-if="activeAdminModal === 'uploadDocument'" class="admin-modal admin-modal-tall" aria-label="上传文档">
        <header class="modal-head">
          <div>
            <h2>{{ editingDocumentId ? "修改文档" : "上传文档" }}</h2>
            <p>{{ editingDocumentId ? "更新文档标题、启用状态和处理配置。" : "上传后解析源文件用于预览；切块参数会保存到文档，点击“切块”时执行。" }}</p>
          </div>
          <button class="modal-close" type="button" aria-label="关闭" @click="closeAdminModal">×</button>
        </header>
        <div class="modal-form single">
          <label v-if="editingDocumentId" class="modal-label">
            文档标题
            <input v-model="editDocumentTitle" class="ui-input modal-control" type="text" placeholder="请输入文档标题" />
          </label>
          <label class="modal-label">
            来源类型
            <select class="ui-input modal-control" disabled>
              <option>Local File</option>
            </select>
          </label>
          <label class="modal-label">
            本地文件
            <input ref="modalUploadFileInput" :accept="uploadAccept" class="ui-input modal-file" type="file" :disabled="!!editingDocumentId" @change="onUploadFileSelected" />
            <span>{{ selectedUploadFileLabel() }}</span>
          </label>
          <div class="modal-config-section">
            <label class="modal-label">
              处理模式
              <select v-model="uploadProcessMode" class="ui-input modal-control">
                <option value="chunk_strategy">按切块策略处理</option>
                <option value="data_channel">按数据通道处理</option>
              </select>
            </label>
            <label v-if="uploadProcessMode === 'chunk_strategy'" class="modal-label">
              切块策略
              <select v-model="uploadChunkStrategy" class="ui-input modal-control">
                <option v-for="option in chunkStrategyOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label v-else class="modal-label">
              数据通道
              <select v-model.number="uploadPipelineId" class="ui-input modal-control" :disabled="ingestionPipelines.length === 0">
                <option v-if="ingestionPipelines.length === 0" :value="null">暂无数据通道</option>
                <option v-for="pipeline in ingestionPipelines" :key="pipeline.id" :value="pipeline.id">
                  {{ pipeline.name }}
                </option>
              </select>
            </label>
            <template v-if="uploadProcessMode === 'chunk_strategy'">
              <template v-if="uploadChunkStrategy === 'structure_aware'">
                <div class="modal-field-grid">
                  <label class="modal-label">
                    理想块大小
                    <input v-model.number="uploadChunkSize" class="ui-input modal-control" min="1" type="number" />
                  </label>
                  <label class="modal-label">
                    块上限
                    <input v-model.number="uploadStructureMaxChars" class="ui-input modal-control" min="1" type="number" />
                  </label>
                </div>
                <div class="modal-field-grid">
                  <label class="modal-label">
                    块下限
                    <input v-model.number="uploadStructureMinChars" class="ui-input modal-control" min="1" type="number" />
                  </label>
                  <label class="modal-label">
                    重叠大小
                    <input v-model.number="uploadChunkOverlap" class="ui-input modal-control" min="0" type="number" />
                  </label>
                </div>
              </template>
              <div v-else-if="uploadShowChunkSizeControls" class="modal-field-grid">
                <label class="modal-label">
                  Chunk Size
                  <input v-model.number="uploadChunkSize" class="ui-input modal-control" min="1" type="number" />
                </label>
                <label class="modal-label">
                  Overlap
                  <input v-model.number="uploadChunkOverlap" class="ui-input modal-control" min="0" type="number" />
                </label>
              </div>
              <label v-if="uploadShowRecursiveSeparatorControls" class="modal-label">
                递归分隔符
                <textarea v-model="uploadRecursiveSeparatorsText" class="ui-input" rows="4"></textarea>
              </label>
              <p class="modal-hint">{{ uploadChunkSummary }}</p>
              <p v-if="uploadAutoStrategyRecommendation" class="modal-hint">{{ uploadAutoStrategyRecommendation }}</p>
              <p v-if="uploadShowRecursiveSeparatorControls" class="modal-hint">{{ uploadRecursiveSeparatorSummary }}</p>
              <p v-if="uploadShowSemanticNotice" class="modal-hint">语义切块会保留策略配置，后端按当前可用能力执行。</p>
            </template>
          </div>
          <label v-if="editingDocumentId" class="modal-checkbox">
            <input v-model="editDocumentEnabled" type="checkbox" />
            启用文档
          </label>
          <p v-if="!editingDocumentId" class="modal-hint">
            上传只保存源文件并解析预览；分块、入库任务和向量化会在点击“切块”后执行。
          </p>
          <p v-if="error" class="modal-hint danger">{{ error }}</p>
        </div>
        <footer class="modal-actions">
          <button class="ghost-btn" type="button" @click="closeAdminModal">取消</button>
          <button class="primary-btn" type="button" :disabled="uploadLoading || (!editingDocumentId && !selectedUploadFile) || (!!editingDocumentId && !editDocumentTitle.trim())" @click="void uploadSelectedDocumentFromModal()">
            {{ editingDocumentId ? "保存" : (uploadLoading ? "上传并解析中..." : "上传") }}
          </button>
        </footer>
      </section>

      <section v-else-if="activeAdminModal === 'pipelineTask'" class="admin-modal admin-modal-wide" aria-label="新建通道任务">
        <header class="modal-head">
          <div>
            <h2>新建通道任务</h2>
            <p>支持 Local File / URL / Feishu / S3 来源，Local File 会直接上传文件。</p>
          </div>
          <button class="modal-close" type="button" aria-label="关闭" @click="closeAdminModal">×</button>
        </header>
        <div class="modal-form single">
          <label class="modal-label">
            流水线
            <select v-model="newPipelineTaskPipelineId" class="ui-input modal-control">
              <option v-for="pipeline in ingestionPipelines" :key="pipeline.id" :value="pipeline.id">
                {{ pipeline.name }}
              </option>
            </select>
          </label>
          <div class="modal-field-grid">
            <label class="modal-label">
              来源类型
              <select v-model="newPipelineTaskSourceType" class="ui-input modal-control">
                <option value="local_file">Local File</option>
                <option value="url" disabled>URL</option>
                <option value="feishu" disabled>Feishu</option>
                <option value="s3" disabled>S3</option>
              </select>
            </label>
            <label class="modal-label">
              本地文件
              <input ref="newPipelineTaskFileInput" :accept="uploadAccept" class="ui-input modal-file" type="file" @change="onPipelineTaskFileSelected" />
            </label>
          </div>
          <label class="modal-label">
            任务元数据（JSON，可选）
            <textarea v-model="newPipelineTaskMetadataText" class="ui-input" rows="5" placeholder='{"source":"manual"}'></textarea>
          </label>
          <p v-if="error" class="modal-hint danger">{{ error }}</p>
        </div>
        <footer class="modal-actions">
          <button class="ghost-btn" type="button" @click="closeAdminModal">取消</button>
          <button
            class="primary-btn"
            type="button"
            :disabled="uploadLoading || !newPipelineTaskPipelineId || !newPipelineTaskFile || !pipelineTaskMetadataValid()"
            @click="void createPipelineTaskFromModal()"
          >
            {{ uploadLoading ? "创建中..." : "创建任务" }}
          </button>
        </footer>
      </section>

      <section v-else-if="activeAdminModal === 'chunkEdit'" class="admin-modal admin-modal-tall" aria-label="修改分块">
        <header class="modal-head">
          <div>
            <h2>修改分块</h2>
            <p>更新分块内容与启用状态。</p>
          </div>
          <button class="modal-close" type="button" aria-label="关闭" @click="closeAdminModal">×</button>
        </header>
        <div class="modal-form single">
          <label class="modal-label">
            分块内容
            <textarea v-model="editChunkContent" class="ui-input" rows="8" placeholder="请输入分块内容"></textarea>
          </label>
          <label class="modal-checkbox">
            <input v-model="editChunkEnabled" type="checkbox" />
            启用分块
          </label>
        </div>
        <footer class="modal-actions">
          <button class="ghost-btn" type="button" @click="closeAdminModal">取消</button>
          <button class="primary-btn" type="button" :disabled="!editChunkContent.trim()" @click="void saveChunkEditFromModal()">保存</button>
        </footer>
      </section>

      <section v-else-if="activeAdminModal === 'intent'" class="admin-modal admin-modal-tall" aria-label="新建意图节点">
        <header class="modal-head">
          <div>
            <h2>新建意图节点</h2>
            <p>当前后端使用知识库 Route Profile 承载意图描述、关键词和示例问题。</p>
          </div>
          <button class="modal-close" type="button" aria-label="关闭" @click="closeAdminModal">×</button>
        </header>
        <div class="modal-form single">
          <div class="modal-field-grid">
            <label class="modal-label">
              节点名称
              <input v-model="newIntentName" class="ui-input modal-control" type="text" placeholder="例如：OA 系统" />
            </label>
            <label class="modal-label">
              意图标识
              <input v-model="newIntentCode" class="ui-input modal-control" type="text" placeholder="例如：biz-oa" />
            </label>
          </div>
          <div class="modal-field-grid">
            <label class="modal-label">
              层级
              <select v-model="newIntentLevel" class="ui-input modal-control">
                <option value="DOMAIN">DOMAIN - 顶层领域</option>
                <option value="CATEGORY">CATEGORY - 分类节点</option>
              </select>
            </label>
            <label class="modal-label">
              类型
              <select v-model="newIntentType" class="ui-input modal-control">
                <option value="KB">KB - 知识库检索</option>
                <option value="MCP">MCP - 工具调用</option>
                <option value="SYSTEM">SYSTEM - 系统交互</option>
              </select>
            </label>
          </div>
          <label class="modal-label">
            父节点
            <select v-model="newIntentParent" class="ui-input modal-control">
              <option value="ROOT">ROOT</option>
              <option v-for="item in adminIntentNodes" :key="item.id" :value="item.id">{{ item.name }}</option>
            </select>
          </label>
          <label class="modal-label">
            知识库
            <select v-model="newIntentKnowledgeBaseId" class="ui-input modal-control">
              <option v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">{{ kb.name }} ({{ kb.id }})</option>
            </select>
          </label>
          <details class="modal-details" open>
            <summary>描述与示例</summary>
            <label class="modal-label">
              描述
              <textarea v-model="newIntentDescription" class="ui-input" rows="3" placeholder="描述这个意图适合回答的问题、业务范围和命中条件"></textarea>
            </label>
            <label class="modal-label">
              示例问题
              <input v-model="newIntentSampleQuestion" class="ui-input modal-control" type="text" placeholder="例如：OA 审批流程怎么配置？" />
            </label>
          </details>
          <details class="modal-details">
            <summary>Prompt 配置</summary>
            <textarea v-model="newIntentPrompt" class="ui-input" rows="4" placeholder="可选，当前后端暂未独立持久化 prompt"></textarea>
          </details>
          <details class="modal-details">
            <summary>高级设置</summary>
            <textarea v-model="newIntentAdvanced" class="ui-input" rows="3" placeholder="可选 JSON，当前后端暂未独立持久化"></textarea>
          </details>
        </div>
        <footer class="modal-actions">
          <button class="ghost-btn" type="button" @click="closeAdminModal">取消</button>
          <button class="primary-btn" type="button" :disabled="!newIntentName.trim() || !routeProfile" @click="void createIntentFromInput()">保存</button>
        </footer>
      </section>

      <section v-else-if="activeAdminModal === 'keyword'" class="admin-modal" aria-label="新增映射规则">
        <header class="modal-head">
          <div>
            <h2>新增映射规则</h2>
            <p>配置查询归一化的关键词映射，保存到当前知识库路由关键词。</p>
          </div>
          <button class="modal-close" type="button" aria-label="关闭" @click="closeAdminModal">×</button>
        </header>
        <div class="modal-form single">
          <label class="modal-label">
            原始词 *
            <input v-model="newKeyword" class="ui-input modal-control" type="text" placeholder="用户输入的原始关键词" />
          </label>
          <label class="modal-label">
            目标词 *
            <input v-model="newKeywordTarget" class="ui-input modal-control" type="text" placeholder="归一化后的目标关键词" />
            <span>当前后端保存原始关键词，目标词作为前端提示字段。</span>
          </label>
          <div class="modal-field-grid">
            <label class="modal-label">
              匹配类型
              <select v-model="newKeywordMatchType" class="ui-input modal-control">
                <option value="exact">精确匹配</option>
                <option value="contains">包含匹配</option>
                <option value="regex">正则匹配</option>
              </select>
            </label>
            <label class="modal-label">
              优先级
              <input v-model.number="newKeywordPriority" class="ui-input modal-control" type="number" />
            </label>
          </div>
          <label class="modal-label">
            启用状态
            <select v-model="newKeywordEnabled" class="ui-input modal-control">
              <option value="enabled">启用</option>
              <option value="disabled">停用</option>
            </select>
          </label>
          <label class="modal-label">
            备注
            <input v-model="newKeywordRemark" class="ui-input modal-control" type="text" placeholder="可选备注信息" />
          </label>
        </div>
        <footer class="modal-actions">
          <button class="ghost-btn" type="button" @click="closeAdminModal">取消</button>
          <button class="primary-btn" type="button" :disabled="!newKeyword.trim()" @click="addKeywordFromInput">保存</button>
        </footer>
      </section>

      <section v-else-if="activeAdminModal === 'user'" class="admin-modal" aria-label="新增用户">
        <header class="modal-head">
          <div>
            <h2>{{ editingUserId ? "修改用户" : "新增用户" }}</h2>
            <p>{{ editingUserId ? "更新用户名称、角色和头像信息。" : "配置账号基本信息。" }}</p>
          </div>
          <button class="modal-close" type="button" aria-label="关闭" @click="closeAdminModal">×</button>
        </header>
        <div class="modal-form single">
          <label class="modal-label">
            用户名
            <input v-model="newAdminUsername" class="ui-input modal-control" type="text" placeholder="请输入用户名" />
          </label>
          <label v-if="!editingUserId" class="modal-label">
            密码
            <input v-model="newAdminPassword" class="ui-input modal-control" type="password" placeholder="设置初始密码" />
          </label>
          <label class="modal-label">
            角色
            <select v-model="newAdminRole" class="ui-input modal-control">
              <option value="user">成员</option>
              <option value="admin">管理员</option>
            </select>
          </label>
          <label class="modal-label">
            头像
            <input v-model="newAdminAvatarUrl" class="ui-input modal-control" type="text" placeholder="可选，填写头像 URL" />
            <span>当前后端暂未保存头像，仅保存用户名、密码和角色。</span>
          </label>
        </div>
        <footer class="modal-actions">
          <button class="ghost-btn" type="button" @click="closeAdminModal">取消</button>
          <button
            class="primary-btn"
            type="button"
            :disabled="!newAdminUsername.trim() || (!editingUserId && !newAdminPassword.trim())"
            @click="void createAdminUserFromInput()"
          >
            {{ editingUserId ? "保存" : "创建" }}
          </button>
        </footer>
      </section>

      <section v-else-if="activeAdminModal === 'sampleQuestion'" class="admin-modal" aria-label="新增示例问题">
        <header class="modal-head">
          <div>
            <h2>新增示例问题</h2>
            <p>配置聊天欢迎页展示的推荐问法。</p>
          </div>
          <button class="modal-close" type="button" aria-label="关闭" @click="closeAdminModal">×</button>
        </header>
        <div class="modal-form single">
          <label class="modal-label">
            标题
            <input v-model="newSampleTitle" class="ui-input modal-control" type="text" placeholder="例如：任务拆解" />
          </label>
          <label class="modal-label">
            描述
            <input v-model="newSampleDescription" class="ui-input modal-control" type="text" placeholder="例如：把目标拆成可执行步骤与优先级" />
          </label>
          <label class="modal-label">
            示例问题
            <textarea v-model="newSampleQuestion" class="ui-input" rows="5" placeholder="请输入示例问题内容"></textarea>
          </label>
        </div>
        <footer class="modal-actions">
          <button class="ghost-btn" type="button" @click="closeAdminModal">取消</button>
          <button class="primary-btn" type="button" :disabled="!newSampleQuestion.trim()" @click="addSampleQuestionFromInput">保存</button>
        </footer>
      </section>
    </div>
  </div>
</template>

<style scoped>
.admin-layout {
  --admin-bg: #f4f7fb;
  --admin-card: #ffffff;
  --admin-ink: #172033;
  --admin-muted: #64748b;
  --admin-border: #dbe4f0;
  --admin-primary: #6d3df5;
  --admin-primary-dark: #5330c6;
  --admin-sidebar: #1d2434;
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
  background: linear-gradient(180deg, #1b2132 0%, #222b3f 100%);
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
  background: rgba(109, 61, 245, 0.28);
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
  background: rgba(255, 255, 255, 0.86);
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
  background: #fff0c2;
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

.admin-grid-two,
.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.trace-list {
  display: grid;
  gap: 14px;
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

.data-table .row-actions {
  display: table-cell;
  white-space: nowrap;
}

.data-table .row-actions button + button {
  margin-left: 5px;
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

.kb-table th:nth-child(1),
.kb-table td:nth-child(1) {
  width: 14%;
}

.kb-table th:nth-child(2),
.kb-table td:nth-child(2) {
  width: 15%;
}

.kb-table th:nth-child(3),
.kb-table td:nth-child(3) {
  width: 11%;
}

.kb-table th:nth-child(4),
.kb-table td:nth-child(4) {
  width: 6%;
}

.kb-table th:nth-child(5),
.kb-table td:nth-child(5) {
  width: 8%;
}

.kb-table th:nth-child(6),
.kb-table td:nth-child(6),
.kb-table th:nth-child(7),
.kb-table td:nth-child(7) {
  width: 13%;
}

.kb-table th:nth-child(8),
.kb-table td:nth-child(8) {
  width: 20%;
}

.kb-table td:nth-child(1),
.kb-table td:nth-child(2) {
  line-height: 1.45;
}

.kb-table td:nth-child(1) .link-btn {
  display: inline;
  white-space: normal;
  word-break: keep-all;
  overflow-wrap: normal;
}

.kb-table td:nth-child(2) {
  word-break: keep-all;
  overflow-wrap: anywhere;
}

.document-table th:nth-child(1),
.document-table td:nth-child(1) {
  width: 17%;
}

.document-table th:nth-child(2),
.document-table td:nth-child(2) {
  width: 7%;
}

.document-table th:nth-child(3),
.document-table td:nth-child(3),
.document-table th:nth-child(4),
.document-table td:nth-child(4) {
  width: 8%;
}

.document-table th:nth-child(5),
.document-table td:nth-child(5) {
  width: 6%;
}

.document-table th:nth-child(6),
.document-table td:nth-child(6),
.document-table th:nth-child(7),
.document-table td:nth-child(7) {
  width: 7%;
}

.document-table th:nth-child(8),
.document-table td:nth-child(8) {
  width: 12%;
}

.document-table th:nth-child(9),
.document-table td:nth-child(9) {
  width: 27%;
}

.pipeline-table th:nth-child(1),
.pipeline-table td:nth-child(1) {
  width: 15%;
}

.pipeline-table th:nth-child(2),
.pipeline-table td:nth-child(2) {
  width: 20%;
}

.pipeline-table th:nth-child(3),
.pipeline-table td:nth-child(3),
.pipeline-table th:nth-child(5),
.pipeline-table td:nth-child(5) {
  width: 7%;
}

.pipeline-table th:nth-child(4),
.pipeline-table td:nth-child(4) {
  width: 10%;
}

.pipeline-table th:nth-child(6),
.pipeline-table td:nth-child(6) {
  width: 15%;
}

.pipeline-table th:nth-child(7),
.pipeline-table td:nth-child(7) {
  width: 13%;
}

.pipeline-task-table th:nth-child(1),
.pipeline-task-table td:nth-child(1) {
  width: 12%;
}

.pipeline-task-table th:nth-child(2),
.pipeline-task-table td:nth-child(2) {
  width: 18%;
}

.pipeline-task-table th:nth-child(3),
.pipeline-task-table td:nth-child(3),
.pipeline-task-table th:nth-child(4),
.pipeline-task-table td:nth-child(4) {
  width: 10%;
}

.pipeline-task-table th:nth-child(5),
.pipeline-task-table td:nth-child(5) {
  width: 12%;
}

.pipeline-task-table th:nth-child(6),
.pipeline-task-table td:nth-child(6) {
  width: 10%;
}

.pipeline-task-table th:nth-child(7),
.pipeline-task-table td:nth-child(7) {
  width: 28%;
}

.pipeline-task-table tbody tr {
  cursor: default;
}

.user-table th:nth-child(1),
.user-table td:nth-child(1) {
  width: 24%;
}

.user-table th:nth-child(2),
.user-table td:nth-child(2) {
  width: 10%;
}

.user-table th:nth-child(3),
.user-table td:nth-child(3),
.user-table th:nth-child(4),
.user-table td:nth-child(4) {
  width: 19%;
}

.user-table th:nth-child(5),
.user-table td:nth-child(5) {
  width: 28%;
}

.trace-table th:nth-child(1),
.trace-table td:nth-child(1) {
  width: 12%;
}

.trace-table th:nth-child(2),
.trace-table td:nth-child(2) {
  width: 15%;
}

.trace-table th:nth-child(3),
.trace-table td:nth-child(3) {
  width: 32%;
}

.trace-table th:nth-child(4),
.trace-table td:nth-child(4) {
  width: 9%;
}

.trace-table th:nth-child(5),
.trace-table td:nth-child(5) {
  width: 7%;
}

.trace-table th:nth-child(6),
.trace-table td:nth-child(6) {
  width: 7%;
}

.trace-table th:nth-child(7),
.trace-table td:nth-child(7) {
  width: 9%;
}

.trace-table th:nth-child(8),
.trace-table td:nth-child(8) {
  width: 9%;
}

.table-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 18px 14px;
  color: #667085;
  font-size: 13px;
  border-top: 1px solid #e9eef6;
}

.table-pagination > div {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.pipeline-table tbody tr {
  cursor: pointer;
}

.pipeline-table tbody tr:hover {
  background: #f8fbff;
}

.wide-cell {
  max-width: 560px;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
  line-height: 1.6;
}

.select-col {
  width: 56px;
  text-align: center !important;
}

.chunk-table td {
  vertical-align: top;
}

.chunk-table th:nth-child(1),
.chunk-table td:nth-child(1) {
  width: 4%;
}

.chunk-table th:nth-child(2),
.chunk-table td:nth-child(2) {
  width: 5%;
}

.chunk-table th:nth-child(3),
.chunk-table td:nth-child(3) {
  width: 25%;
}

.chunk-table th:nth-child(4),
.chunk-table td:nth-child(4) {
  width: 7%;
}

.chunk-table th:nth-child(5),
.chunk-table td:nth-child(5) {
  width: 6%;
}

.chunk-table th:nth-child(6),
.chunk-table td:nth-child(6) {
  width: 9%;
}

.chunk-table th:nth-child(7),
.chunk-table td:nth-child(7) {
  width: 18%;
}

.chunk-table th:nth-child(8),
.chunk-table td:nth-child(8) {
  width: 12%;
}

.chunk-table th:nth-child(9),
.chunk-table td:nth-child(9) {
  width: 14%;
}

.chunk-table th:nth-child(3),
.chunk-table td:nth-child(3) {
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.chunk-table th:nth-child(7),
.chunk-table td:nth-child(7) {
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.chunk-content {
  max-width: 520px;
  color: #38506f;
  line-height: 1.65;
}

.chunk-content-preview {
  display: -webkit-box;
  max-height: 7.95em;
  overflow: hidden;
  white-space: pre-wrap;
  word-break: break-word;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 5;
}

.empty-cell {
  padding: 32px !important;
  color: var(--admin-muted);
  text-align: center !important;
}

.document-preview-box {
  max-height: min(62vh, 620px);
  overflow: auto;
  border: 1px solid #dce5f2;
  border-radius: 12px;
  background: #f8fbff;
}

.document-preview-box pre {
  margin: 0;
  padding: 16px;
  color: #26364f;
  font: 14px/1.7 Consolas, "Courier New", monospace;
  white-space: pre-wrap;
  word-break: break-word;
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

.intent-tree-box {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.intent-tree-group {
  display: grid;
  gap: 8px;
}

.intent-node {
  display: grid;
  gap: 4px;
  border: 1px solid #dbe4f0;
  border-radius: 12px;
  padding: 12px 14px;
  background: #fbfdff;
}

.intent-node span {
  color: var(--admin-muted);
  font-size: 13px;
}

.intent-tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.intent-tag,
.intent-parent-label {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  border-radius: 999px;
  padding: 0 8px;
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
  line-height: 20px;
}

.intent-tag {
  border: 1px solid #dbe4f0;
  background: #ffffff;
  color: #52627c;
}

.intent-tag.level-domain {
  border-color: rgba(49, 94, 251, 0.28);
  background: #eef3ff;
  color: #315efb;
}

.intent-tag.level-category {
  border-color: rgba(0, 168, 126, 0.28);
  background: #eafaf5;
  color: #067a60;
}

.intent-tag.type-mcp {
  border-color: rgba(213, 125, 17, 0.28);
  background: #fff5e8;
  color: #a65f09;
}

.intent-tag.type-system {
  border-color: rgba(114, 74, 214, 0.28);
  background: #f4f0ff;
  color: #6841c6;
}

.intent-tag.type-kb {
  border-color: rgba(91, 114, 143, 0.24);
  background: #f8fafc;
  color: #52627c;
}

.intent-tag.disabled {
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #94a3b8;
}

.intent-parent-label {
  background: #f8fafc;
  color: #64748b;
}

.intent-parent-label::before {
  content: "父级 ";
  color: #94a3b8;
  font-weight: 700;
}

.root-node {
  border-color: rgba(109, 61, 245, 0.34);
  background: linear-gradient(135deg, #f6f2ff 0%, #ffffff 100%);
}

.intent-child-list {
  display: grid;
  gap: 8px;
  margin-left: 24px;
  padding-left: 18px;
  border-left: 1px solid rgba(148, 163, 184, 0.42);
}

.child-node {
  position: relative;
  margin-left: 0;
}

.intent-child-list .child-node::before {
  content: "";
  position: absolute;
  left: -19px;
  top: 24px;
  width: 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.42);
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

.trace-detail-head h1 {
  display: flex;
  align-items: center;
  gap: 10px;
}

.trace-summary-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  overflow: hidden;
  border: 1px solid var(--admin-border);
  border-radius: 12px;
  margin-bottom: 18px;
  background: white;
}

.trace-summary-strip article {
  padding: 14px 18px;
  border-right: 1px solid var(--admin-border);
}

.trace-summary-strip article:last-child {
  border-right: 0;
}

.trace-summary-strip span {
  color: var(--admin-muted);
  font-size: 13px;
}

.trace-summary-strip strong {
  display: block;
  margin-top: 6px;
  color: #172033;
  font-size: 22px;
}

.trace-detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}

.trace-timeline-card {
  min-width: 0;
}

.trace-timeline {
  padding: 18px 22px 22px;
}

.trace-axis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  margin-left: 260px;
  margin-bottom: 10px;
  color: #8a99b4;
  font-size: 12px;
}

.trace-node-row {
  display: grid;
  grid-template-columns: 240px minmax(220px, 1fr) 128px;
  align-items: center;
  gap: 14px;
  padding: 12px 0;
  border-top: 1px solid #eef3fa;
}

.trace-node-name {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 4px 10px;
  align-items: center;
}

.trace-node-name strong {
  color: #172033;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-node-name small {
  grid-column: 2;
  display: inline-flex;
  width: fit-content;
  border-radius: 7px;
  padding: 4px 8px;
  background: #eef3fa;
  color: #52627c;
  font-size: 12px;
}

.trace-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #20c997;
}

.trace-bar-track {
  position: relative;
  height: 24px;
  border-radius: 8px;
  background: linear-gradient(90deg, #f5f8fc 0%, #f5f8fc 24%, #e6edf7 24%, #e6edf7 25%, #f5f8fc 25%, #f5f8fc 49%, #e6edf7 49%, #e6edf7 50%, #f5f8fc 50%, #f5f8fc 74%, #e6edf7 74%, #e6edf7 75%, #f5f8fc 75%);
  overflow: hidden;
}

.trace-bar {
  position: absolute;
  top: 5px;
  height: 14px;
  min-width: 6px;
  border-radius: 999px;
  background: linear-gradient(90deg, #20c997, #38d9a9);
}

.trace-node-duration {
  display: grid;
  gap: 2px;
  text-align: right;
}

.trace-node-duration strong {
  color: #172033;
}

.trace-node-duration small {
  color: #8a99b4;
  font-size: 12px;
}

.trace-message-list {
  display: grid;
  gap: 10px;
  padding: 18px 24px 24px;
}

.trace-message-item {
  display: grid;
  grid-template-columns: 84px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  border: 1px solid #e8eef7;
  border-radius: 12px;
  padding: 12px;
  background: #fbfdff;
}

.trace-message-item.assistant {
  background: #f8fbff;
}

.trace-message-item p {
  margin: 6px 0 0;
  color: #52627c;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.setting-list {
  display: grid;
  grid-template-columns: minmax(180px, 0.7fr) minmax(0, 1fr);
  gap: 10px 16px;
  margin: 18px 0 0;
}

.setting-list dt {
  color: #52627c;
  font-weight: 700;
}

.setting-list dd {
  margin: 0;
  color: #172033;
  word-break: break-word;
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
  color: #413cff;
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

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  padding: 28px;
  background: rgba(15, 23, 42, 0.48);
  backdrop-filter: blur(6px);
}

.admin-modal {
  width: min(1040px, 100%);
  max-height: min(860px, calc(100vh - 56px));
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  gap: 18px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 24px;
  padding: 26px;
  background: #ffffff;
  box-shadow: 0 28px 90px rgba(15, 23, 42, 0.22);
  overflow: hidden;
}

.admin-modal:not(.admin-modal-wide) {
  width: min(560px, 100%);
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 22px;
  padding: 30px;
}

.admin-modal-tall {
  width: min(760px, 100%) !important;
}

.admin-modal-wide {
  width: min(1040px, 100%);
}

.modal-head,
.node-panel-head,
.modal-actions,
.node-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.modal-head h2,
.node-panel-head h3 {
  margin: 0;
  color: #172033;
}

.modal-head p,
.node-panel-head p {
  margin: 8px 0 0;
  color: #64748b;
  line-height: 1.6;
}

.modal-close {
  width: 40px;
  height: 40px;
  border: 1px solid var(--admin-border);
  border-radius: 999px;
  background: #fff;
  color: #475569;
  cursor: pointer;
  font-size: 24px;
  line-height: 1;
}

.modal-form {
  display: grid;
  grid-template-columns: minmax(240px, 0.8fr) minmax(0, 1.2fr);
  gap: 16px;
  min-height: 0;
  overflow: auto;
  padding-right: 4px;
}

.modal-form.single {
  grid-template-columns: 1fr;
  gap: 20px;
}

.modal-label {
  display: grid;
  gap: 8px;
  color: #30405b;
  font-weight: 700;
}

.modal-label span,
.modal-hint {
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.55;
}

.modal-hint.danger {
  border: 1px solid #fecaca;
  border-radius: 10px;
  padding: 10px 12px;
  background: #fff5f5;
  color: #dc2626;
  font-weight: 700;
}

.modal-control {
  min-height: 54px;
  border-radius: 16px;
  padding-inline: 18px;
  box-shadow: 0 6px 14px rgba(15, 23, 42, 0.04);
}

.modal-file {
  display: flex;
  align-items: center;
  min-height: 54px;
  border-radius: 16px;
  padding: 12px 18px;
}

.modal-field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.modal-config-section {
  display: grid;
  gap: 20px;
}

.modal-details {
  border: 1px solid var(--admin-border);
  border-radius: 14px;
  padding: 0;
  background: #fbfdff;
  overflow: hidden;
}

.modal-details summary {
  cursor: pointer;
  padding: 16px 18px;
  color: #172033;
  font-weight: 800;
}

.modal-details[open] {
  padding-bottom: 16px;
}

.modal-details[open] summary {
  margin-bottom: 12px;
  border-bottom: 1px solid #e8eef7;
}

.modal-details .modal-label,
.modal-details textarea {
  margin-inline: 18px;
}

.modal-label.wide,
.pipeline-node-grid .wide {
  grid-column: 1 / -1;
}

.pipeline-node-panel {
  display: grid;
  gap: 14px;
  min-height: 0;
  padding: 18px;
  border: 1px solid var(--admin-border);
  border-radius: 18px;
  background: #f8fafc;
  overflow: auto;
}

.pipeline-node-card {
  display: grid;
  gap: 16px;
  padding: 16px;
  border: 1px solid #dbe4f0;
  border-radius: 16px;
  background: #ffffff;
}

.node-card-head > div {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pipeline-node-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.pipeline-json-mini,
.pipeline-json-textarea {
  font-family: "JetBrains Mono", "Cascadia Code", Consolas, monospace;
  line-height: 1.55;
}

.pipeline-json-textarea {
  min-height: 360px;
  resize: vertical;
}

.empty-node-box {
  border: 1px dashed #cbd5e1;
  border-radius: 14px;
  padding: 28px;
  color: #64748b;
  text-align: center;
  background: #fff;
}

.readonly-node-panel {
  max-height: 62vh;
  overflow: auto;
}

.node-detail-list {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px 12px;
  margin: 12px 0 0;
  color: var(--admin-text);
}

.node-detail-list dt {
  color: var(--admin-muted);
  font-size: 12px;
}

.node-detail-list dd {
  margin: 0;
  min-width: 0;
  word-break: break-word;
}

.node-detail-list pre {
  margin: 0;
  padding: 10px;
  max-height: 180px;
  overflow: auto;
  border-radius: 8px;
  background: #f8fafc;
  font-size: 12px;
}

.modal-actions {
  justify-content: flex-end;
  padding-top: 4px;
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
  background: linear-gradient(90deg, #1f9d8a, #6d3df5);
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
  background: linear-gradient(180deg, #6d3df5, #3b1ea8);
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
  background: #6d3df5;
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
  border: 1px solid rgba(109, 61, 245, 0.12);
  border-radius: 14px;
  background: rgba(109, 61, 245, 0.04);
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
  border-color: rgba(109, 61, 245, 0.55);
  background: rgba(109, 61, 245, 0.08);
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
  background: #eef2ff;
  color: #3730a3;
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

.modal-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--admin-ink);
  font-weight: 700;
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
  .admin-grid-two,
  .admin-grid-three,
  .settings-grid,
  .dashboard-hero-grid,
  .trace-detail-grid,
  .trace-summary-strip,
  .form-panel {
    grid-template-columns: 1fr;
  }

  .trace-axis {
    margin-left: 0;
  }

  .trace-node-row {
    grid-template-columns: 1fr;
  }

  .trace-node-duration {
    text-align: left;
  }

  .page-head,
  .table-toolbar,
  .admin-header,
  .modal-head,
  .node-panel-head,
  .modal-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .modal-form,
  .pipeline-node-grid,
  .modal-field-grid {
    grid-template-columns: 1fr;
  }
}
</style>
