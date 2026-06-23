import { computed, onMounted, ref, shallowRef, watch } from "vue";

import {
  clearAdminIntentTreeCache,
  changeAdminUserPassword,
  createAdminIntentNode,
  createAdminKeywordMapping,
  createKnowledgeBase,
  createAdminUser,
  createIngestionPipeline,
  createKnowledgeDocument,
  deleteIngestionPipeline,
  deleteAdminUser,
  deleteAdminIntentNode,
  deleteAdminKeywordMapping,
  deleteKnowledgeBase,
  deleteKnowledgeDocument,
  fetchAdminDashboard,
  fetchAdminIntentNodes,
  fetchAdminIntentTreeCacheStatus,
  fetchAdminKeywordMappings,
  fetchAdminTraceDetail,
  fetchAdminTraceNodes,
  fetchAdminSettings,
  fetchAdminTraces,
  fetchAdminUsers,
  fetchIngestionTaskNodes,
  fetchIngestionPipelines,
  fetchIngestionTasks,
  fetchKnowledgeBases,
  fetchKnowledgeChunks,
  fetchKnowledgeDocuments,
  fetchMeta,
  reindexKnowledgeDocument,
  updateKnowledgeBase,
  updateKnowledgeDocument,
  updateKnowledgeChunk,
  updateIngestionPipeline,
  updateAdminUser,
  updateAdminUserRole,
  type AdminUserCreateRequest,
  type AdminUserPasswordChangeRequest,
  type AdminUserUpdateRequest,
  type IngestionPipelineCreateRequest,
  type KnowledgeChunkingOptions,
  type KnowledgeDocumentUpdatePayload,
  uploadKnowledgeDocument,
  fetchRouteProfile,
  updateRouteProfile,
  updateAdminIntentNode,
  updateAdminKeywordMapping,
  type AdminIntentNodeUpsertRequest,
  type AdminKeywordMappingUpsertRequest,
  type KnowledgeBaseRouteProfile
} from "../services/api";
import { useAuthStore } from "../stores/auth";

const DEFAULT_CHUNK_SIZE = 512;
const DEFAULT_CHUNK_OVERLAP = 128;
const DEFAULT_STRUCTURE_TARGET_CHARS = 1400;
const DEFAULT_STRUCTURE_MAX_CHARS = 1800;
const DEFAULT_STRUCTURE_MIN_CHARS = 600;
const DEFAULT_RECURSIVE_SEPARATOR_TEXT = ["\\n\\n", "\\n", "。", "；", "，", ". ", "! ", "? ", "[space]"].join("\n");

const documentTypeOptions = [
  { value: "manual", label: "普通文本" },
  { value: "knowledge_base", label: "产品手册 / 知识库" },
  { value: "faq", label: "FAQ / 问答" },
  { value: "contract", label: "合同 / 法律文本" },
  { value: "log", label: "日志" },
  { value: "html", label: "HTML 页面" },
  { value: "ocr", label: "OCR / 格式混乱文本" },
  { value: "mixed_knowledge", label: "混合企业知识" }
] as const;

const chunkStrategyOptions = [
  { value: "structure_aware", label: "结构感知分块" },
  { value: "fixed_size", label: "固定大小分块" },
  { value: "overlap", label: "重叠分块" },
  { value: "recursive", label: "递归分块" },
  { value: "semantic_embedding", label: "Embedding 语义分块" },
  { value: "hybrid_recursive_semantic", label: "递归 + 语义混合分块" }
] as const;

const autoStrategyRecommendations: Record<string, string> = {
  manual: "普通文本推荐递归分块，优先按段落和句子边界切分。",
  knowledge_base: "知识库文档推荐结构感知分块，兼顾标题、段落和上下文连续性。",
  faq: "FAQ 推荐递归分块，便于保留问题与答案的成对关系。",
  contract: "合同 / 法律文本推荐 Embedding 语义分块，更适合按条款语义聚合。",
  log: "日志推荐固定大小分块，便于稳定切片和时序检索。",
  html: "HTML 页面推荐结构感知分块，优先保留标题层级和段落结构。",
  ocr: "OCR 文本推荐重叠分块，用重叠窗口缓解识别噪声造成的断句问题。",
  mixed_knowledge: "混合企业知识推荐递归 + 语义混合分块，先按结构粗切，再做语义细切。"
};
function normalizeChunkSettings(chunkSize: number, chunkOverlap: number, maxChunkSize = 1000) {
  if (chunkSize === -1) {
    return { chunkSize: -1, chunkOverlap: 0 };
  }
  const safeChunkSize = Number.isFinite(chunkSize)
    ? Math.max(200, Math.min(maxChunkSize, Math.floor(chunkSize)))
    : DEFAULT_CHUNK_SIZE;
  const maxAllowedOverlap = Math.max(0, safeChunkSize - 1);
  const recommendedOverlap = Math.min(Math.floor(safeChunkSize * 0.25), maxAllowedOverlap);
  const safeChunkOverlap = Number.isFinite(chunkOverlap)
    ? Math.max(0, Math.min(maxAllowedOverlap, Math.floor(chunkOverlap)))
    : Math.min(DEFAULT_CHUNK_OVERLAP, recommendedOverlap);

  return {
    chunkSize: safeChunkSize,
    chunkOverlap: safeChunkOverlap
  };
}
function buildChunkConfig(
  strategy: string,
  chunkSize: number,
  chunkOverlap: number,
  recursiveSeparatorsText: string,
  structureMaxChars = DEFAULT_STRUCTURE_MAX_CHARS,
  structureMinChars = DEFAULT_STRUCTURE_MIN_CHARS
) {
  if (strategy === "fixed_size") {
    return {
      chunkSize,
      overlapSize: chunkSize === -1 ? 0 : chunkOverlap
    };
  }
  if (strategy === "structure_aware") {
    return {
      targetChars: chunkSize,
      overlapChars: chunkOverlap,
      maxChars: structureMaxChars,
      minChars: structureMinChars
    };
  }
  if (["recursive", "hybrid_recursive_semantic"].includes(strategy)) {
    return {
      chunk_size: chunkSize,
      chunk_overlap: chunkOverlap,
      recursive_separators: parseRecursiveSeparatorsText(recursiveSeparatorsText)
    };
  }
  return {
    chunk_size: chunkSize,
    chunk_overlap: chunkOverlap
  };
}

function parseRecursiveSeparatorsText(value: string): string[] {
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

const hasSavedProcessingConfig = (config?: KnowledgeChunkingOptions | null): config is KnowledgeChunkingOptions =>
  Boolean(config && Object.keys(config).length > 0);

const normalizeSavedProcessingConfig = (config: KnowledgeChunkingOptions): KnowledgeChunkingOptions => ({
  documentType: config.documentType ?? "knowledge_base",
  processMode: config.processMode ?? "chunk_strategy",
  pipelineId: config.processMode === "data_channel" ? config.pipelineId : undefined,
  chunkStrategy: config.chunkStrategy ?? "structure_aware",
  chunkSize: config.chunkSize ?? DEFAULT_CHUNK_SIZE,
  chunkOverlap: config.chunkOverlap ?? 0,
  recursiveSeparators: config.recursiveSeparators ?? parseRecursiveSeparatorsText(DEFAULT_RECURSIVE_SEPARATOR_TEXT),
  chunkConfig: config.chunkConfig ?? {}
});

function createChunkingPresentation(
  strategy: ReturnType<typeof shallowRef<string>>,
  documentType: ReturnType<typeof shallowRef<string>>,
  chunkSize: ReturnType<typeof shallowRef<number>>,
  chunkOverlap: ReturnType<typeof shallowRef<number>>,
  recursiveSeparatorsText: ReturnType<typeof shallowRef<string>>
) {
  const showChunkSizeControls = computed(() => strategy.value !== "");
  const showRecursiveSeparatorControls = computed(() =>
    ["recursive", "hybrid_recursive_semantic"].includes(strategy.value)
  );
  const showSemanticNotice = computed(() =>
    ["semantic_embedding", "hybrid_recursive_semantic"].includes(strategy.value)
  );
  const autoStrategyRecommendation = computed(() =>
    strategy.value === "auto" ? autoStrategyRecommendations[documentType.value] ?? "将回退到递归分块。" : ""
  );
  const recursiveSeparatorSummary = computed(() => {
    const separators = parseRecursiveSeparatorsText(recursiveSeparatorsText.value);
    return separators.length > 0 ? `${separators.length} 个分隔符` : "使用默认分隔符";
  });
  const chunkSummary = computed(
    () => {
      if (strategy.value === "structure_aware") {
        return `target ${chunkSize.value} / overlap ${chunkOverlap.value}，优先按标题、段落和代码块边界打包。`;
      }
      if (strategy.value === "fixed_size") {
        return chunkSize.value === -1
          ? "不切分，整篇文档作为一个分块。"
          : `chunkSize ${chunkSize.value} / overlapSize ${chunkOverlap.value}，按字符窗口稳定切片。`;
      }
      return `chunk size ${chunkSize.value} / overlap ${chunkOverlap.value}，建议 overlap 约为 chunk size 的 10% - 25%。`;
    }
  );

  return {
    showChunkSizeControls,
    showRecursiveSeparatorControls,
    showSemanticNotice,
    autoStrategyRecommendation,
    recursiveSeparatorSummary,
    chunkSummary
  };
}

export function useRetriFlowAdmin() {
  const authStore = useAuthStore();

  const loading = shallowRef(true);
  const documentLoading = shallowRef(false);
  const chunkLoading = shallowRef(false);
  const taskNodeLoading = shallowRef(false);
  const uploadLoading = shallowRef(false);
  const reindexLoading = shallowRef(false);
  const reindexingDocumentId = shallowRef<number | null>(null);
  const error = shallowRef("");
  const infoMessage = shallowRef("");

  const meta = ref<Awaited<ReturnType<typeof fetchMeta>> | null>(null);
  const knowledgeBases = ref<Awaited<ReturnType<typeof fetchKnowledgeBases>>["items"]>([]);
  const selectedKnowledgeBaseId = shallowRef("");
  const selectedDocumentId = shallowRef<number | null>(null);
  const documents = ref<Awaited<ReturnType<typeof fetchKnowledgeDocuments>>["items"]>([]);
  const chunks = ref<Awaited<ReturnType<typeof fetchKnowledgeChunks>>["items"]>([]);
  const ingestionPipelines = ref<Awaited<ReturnType<typeof fetchIngestionPipelines>>["items"]>([]);
  const ingestionTasks = ref<Awaited<ReturnType<typeof fetchIngestionTasks>>["items"]>([]);
  const selectedDocumentTask = shallowRef<Awaited<ReturnType<typeof fetchIngestionTasks>>["items"][number] | null>(null);
  const ingestionTaskNodes = ref<Awaited<ReturnType<typeof fetchIngestionTaskNodes>>["items"]>([]);
  const adminUsers = ref<Awaited<ReturnType<typeof fetchAdminUsers>>["items"]>([]);
  const adminDashboard = ref<Awaited<ReturnType<typeof fetchAdminDashboard>> | null>(null);
  const dashboardRange = shallowRef("24h");
  const adminIntentNodes = ref<Awaited<ReturnType<typeof fetchAdminIntentNodes>>["items"]>([]);
  const adminIntentTreeCacheStatus = ref<Awaited<ReturnType<typeof fetchAdminIntentTreeCacheStatus>> | null>(null);
  const adminKeywordMappings = ref<Awaited<ReturnType<typeof fetchAdminKeywordMappings>>["items"]>([]);
  const adminTraces = ref<Awaited<ReturnType<typeof fetchAdminTraces>>["items"]>([]);
  const adminTraceTotal = shallowRef(0);
  const adminTracePage = shallowRef(1);
  const adminTracePageSize = shallowRef(10);
  const adminTraceId = shallowRef("");
  const selectedAdminTrace = ref<Awaited<ReturnType<typeof fetchAdminTraceDetail>> | null>(null);
  const selectedAdminTraceNodes = ref<Awaited<ReturnType<typeof fetchAdminTraceNodes>>["items"]>([]);
  const adminSettings = ref<Awaited<ReturnType<typeof fetchAdminSettings>>["items"]>([]);

  const documentTitle = shallowRef("");
  const documentContent = shallowRef("");
  const documentType = shallowRef("manual");
  const chunkStrategy = shallowRef("auto");
  const chunkSize = shallowRef(DEFAULT_CHUNK_SIZE);
  const chunkOverlap = shallowRef(DEFAULT_CHUNK_OVERLAP);
  const recursiveSeparatorsText = shallowRef(DEFAULT_RECURSIVE_SEPARATOR_TEXT);

  const uploadFileName = shallowRef("");
  const uploadProcessMode = shallowRef<"chunk_strategy" | "data_channel">("chunk_strategy");
  const uploadPipelineId = shallowRef<number | null>(null);
  const uploadChunkStrategy = shallowRef("structure_aware");
  const uploadChunkSize = shallowRef(DEFAULT_STRUCTURE_TARGET_CHARS);
  const uploadChunkOverlap = shallowRef(0);
  const uploadStructureMaxChars = shallowRef(DEFAULT_STRUCTURE_MAX_CHARS);
  const uploadStructureMinChars = shallowRef(DEFAULT_STRUCTURE_MIN_CHARS);
  const uploadRecursiveSeparatorsText = shallowRef(DEFAULT_RECURSIVE_SEPARATOR_TEXT);

  const documentProcessMode = shallowRef<"chunk_strategy" | "data_channel">("chunk_strategy");
  const documentPipelineId = shallowRef<number | null>(null);
  const documentChunkStrategy = shallowRef("structure_aware");
  const documentChunkSize = shallowRef(DEFAULT_STRUCTURE_TARGET_CHARS);
  const documentChunkOverlap = shallowRef(0);
  const documentStructureMaxChars = shallowRef(DEFAULT_STRUCTURE_MAX_CHARS);
  const documentStructureMinChars = shallowRef(DEFAULT_STRUCTURE_MIN_CHARS);
  const documentRecursiveSeparatorsText = shallowRef(DEFAULT_RECURSIVE_SEPARATOR_TEXT);

  const isAdmin = computed(() => authStore.isAdmin);
  const canManageKnowledge = computed(() => isAdmin.value);
  const canViewIngestion = computed(() => isAdmin.value);
  const readonlyNotice = computed(() =>
    canManageKnowledge.value
      ? ""
      : "你当前处于只读模式：可以查看知识库、文档和分块内容，但不能新建知识库、上传文档、手动入库或查看 ingestion 日志。"
  );

  const selectedKnowledgeBase = computed(() =>
    knowledgeBases.value.find((item) => item.id === selectedKnowledgeBaseId.value) ?? null
  );
  const selectedDocument = computed(() =>
    documents.value.find((item) => item.id === selectedDocumentId.value) ?? null
  );
  const canCreateDocument = computed(() =>
    Boolean(
      canManageKnowledge.value &&
        selectedKnowledgeBaseId.value &&
        documentTitle.value.trim() &&
        documentContent.value.trim()
    )
  );
  const relatedTask = computed(
    () => selectedDocumentTask.value ?? ingestionTasks.value.find((item) => item.document_id === selectedDocumentId.value) ?? null
  );
  const canReindexDocument = computed(() =>
    Boolean(
      canManageKnowledge.value &&
        selectedKnowledgeBaseId.value &&
        selectedDocumentId.value !== null &&
        !reindexLoading.value
    )
  );

  const manualPresentation = createChunkingPresentation(
    chunkStrategy,
    documentType,
    chunkSize,
    chunkOverlap,
    recursiveSeparatorsText
  );
  const uploadPresentation = createChunkingPresentation(
    uploadChunkStrategy,
    shallowRef("knowledge_base"),
    uploadChunkSize,
    uploadChunkOverlap,
    uploadRecursiveSeparatorsText
  );

  function denyManagementAction() {
    error.value = "当前账号没有后台管理权限，请使用 admin 账号执行知识库维护操作。";
  }

  const loadTaskNodes = async (taskId: number | null) => {
    if (!canViewIngestion.value || taskId === null) {
      ingestionTaskNodes.value = [];
      return;
    }

    taskNodeLoading.value = true;
    error.value = "";

    try {
      const nodeData = await fetchIngestionTaskNodes(taskId);
      ingestionTaskNodes.value = nodeData.items;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "加载 ingestion 节点日志失败";
    } finally {
      taskNodeLoading.value = false;
    }
  };

  const loadSelectedDocumentTask = async (documentId: number | null) => {
    if (!canViewIngestion.value || documentId === null) {
      selectedDocumentTask.value = null;
      ingestionTaskNodes.value = [];
      return;
    }

    try {
      const taskData = await fetchIngestionTasks({ documentId });
      selectedDocumentTask.value = taskData.items[0] ?? null;
      await loadTaskNodes(selectedDocumentTask.value?.id ?? null);
    } catch (err) {
      selectedDocumentTask.value = null;
      ingestionTaskNodes.value = [];
      error.value = err instanceof Error ? err.message : "加载文档入库任务失败";
    }
  };

  const loadAdminTraces = async (page = adminTracePage.value) => {
    if (!isAdmin.value) {
      adminTraces.value = [];
      adminTraceTotal.value = 0;
      return;
    }

    const traceData = await fetchAdminTraces({
      page,
      pageSize: adminTracePageSize.value,
      traceId: adminTraceId.value
    });
    adminTraces.value = traceData.items;
    adminTraceTotal.value = traceData.total;
    adminTracePage.value = traceData.page;
    adminTracePageSize.value = traceData.page_size;
  };

  const searchAdminTraces = async () => {
    await loadAdminTraces(1);
  };

  const createPipeline = async (payload: IngestionPipelineCreateRequest) => {
    if (!canViewIngestion.value) {
      denyManagementAction();
      return;
    }
    error.value = "";
    infoMessage.value = "";
    try {
      const created = await createIngestionPipeline(payload);
      ingestionPipelines.value = [...ingestionPipelines.value, created];
      infoMessage.value = "流水线已创建。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "新增流水线失败";
    }
  };

  const updatePipeline = async (pipelineId: number, payload: IngestionPipelineCreateRequest) => {
    if (!canViewIngestion.value) {
      denyManagementAction();
      return;
    }
    error.value = "";
    infoMessage.value = "";
    try {
      const updated = await updateIngestionPipeline(pipelineId, payload);
      ingestionPipelines.value = ingestionPipelines.value.map((item) => (item.id === pipelineId ? updated : item));
      infoMessage.value = "流水线已更新。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "更新流水线失败";
    }
  };

  const removePipeline = async (pipelineId: number) => {
    if (!canViewIngestion.value) {
      denyManagementAction();
      return;
    }
    error.value = "";
    infoMessage.value = "";
    try {
      await deleteIngestionPipeline(pipelineId);
      ingestionPipelines.value = ingestionPipelines.value.filter((item) => item.id !== pipelineId);
      infoMessage.value = "流水线已删除。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "删除流水线失败";
    }
  };

  const loadChunks = async (knowledgeBaseId: string, documentId: number | null) => {
    if (!knowledgeBaseId || documentId === null) {
      chunks.value = [];
      return;
    }

    chunkLoading.value = true;
    error.value = "";

    try {
      const chunkData = await fetchKnowledgeChunks(knowledgeBaseId, documentId);
      chunks.value = chunkData.items;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "加载文档分块失败";
    } finally {
      chunkLoading.value = false;
    }
  };

  const loadDocuments = async (knowledgeBaseId: string) => {
    if (!knowledgeBaseId) {
      documents.value = [];
      selectedDocumentId.value = null;
      return;
    }

    documentLoading.value = true;
    error.value = "";

    try {
      const documentData = await fetchKnowledgeDocuments(knowledgeBaseId);
      documents.value = documentData.items;
      selectedDocumentId.value = documentData.items[0]?.id ?? null;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "加载知识库文档列表失败";
    } finally {
      documentLoading.value = false;
    }
  };

  const load = async () => {
    loading.value = true;
    error.value = "";

    try {
      const [metaData, knowledgeData] = await Promise.all([fetchMeta(), fetchKnowledgeBases()]);
      meta.value = metaData;
      knowledgeBases.value = knowledgeData.items;
      if (isAdmin.value) {
        const [
          pipelineData,
          taskData,
          userData,
          dashboardData,
          intentNodeData,
          intentTreeCacheData,
          keywordMappingData,
          traceData,
          settingData
        ] = await Promise.all([
          fetchIngestionPipelines(),
          fetchIngestionTasks(),
          fetchAdminUsers(),
          fetchAdminDashboard(dashboardRange.value),
          fetchAdminIntentNodes(),
          fetchAdminIntentTreeCacheStatus(),
          fetchAdminKeywordMappings(),
          fetchAdminTraces({
            page: adminTracePage.value,
            pageSize: adminTracePageSize.value,
            traceId: adminTraceId.value
          }),
          fetchAdminSettings()
        ]);
        ingestionPipelines.value = pipelineData.items;
        ingestionTasks.value = taskData.items;
        adminUsers.value = userData.items;
        adminDashboard.value = dashboardData;
        adminIntentNodes.value = intentNodeData.items;
        adminIntentTreeCacheStatus.value = intentTreeCacheData;
        adminKeywordMappings.value = keywordMappingData.items;
        adminTraces.value = traceData.items;
        adminTraceTotal.value = traceData.total;
        adminTracePage.value = traceData.page;
        adminTracePageSize.value = traceData.page_size;
        adminSettings.value = settingData.items;
      } else {
        ingestionPipelines.value = [];
        ingestionTasks.value = [];
        adminUsers.value = [];
        adminDashboard.value = null;
        adminIntentNodes.value = [];
        adminIntentTreeCacheStatus.value = null;
        adminKeywordMappings.value = [];
        adminTraces.value = [];
        adminTraceTotal.value = 0;
        adminSettings.value = [];
      }

      if (!selectedKnowledgeBaseId.value && knowledgeData.items.length > 0) {
        selectedKnowledgeBaseId.value = knowledgeData.items[0].id;
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : "加载 RetriFlow 后台数据失败";
    } finally {
      loading.value = false;
    }
  };

  const refreshKnowledgeData = async (documentId?: number) => {
    await load();
    await loadDocuments(selectedKnowledgeBaseId.value);
    if (documentId) {
      selectedDocumentId.value = documentId;
      await loadChunks(selectedKnowledgeBaseId.value, documentId);
    }
  };

  const addKnowledgeBase = async (
    payload?: string | { name: string; embeddingModel: string; collectionName: string }
  ) => {
    if (!canManageKnowledge.value) {
      denyManagementAction();
      return;
    }

    const created =
      typeof payload === "object"
        ? await createKnowledgeBase(payload)
        : await createKnowledgeBase(payload?.trim() || `RetriFlow 知识库 ${knowledgeBases.value.length + 1}`);
    selectedKnowledgeBaseId.value = created.id;
    infoMessage.value = "知识库已创建。";
    await load();
  };

  const saveKnowledgeBase = async (
    knowledgeBaseId: string,
    payload: { name: string; embeddingModel: string; collectionName: string }
  ) => {
    if (!canManageKnowledge.value) {
      denyManagementAction();
      return null;
    }
    error.value = "";
    infoMessage.value = "";
    try {
      const updated = await updateKnowledgeBase(knowledgeBaseId, payload);
      knowledgeBases.value = knowledgeBases.value.map((item) => (item.id === updated.id ? updated : item));
      infoMessage.value = "知识库已更新。";
      return updated;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "更新知识库失败";
      return null;
    }
  };

  const removeKnowledgeBase = async (knowledgeBaseId: string) => {
    if (!canManageKnowledge.value) {
      denyManagementAction();
      return;
    }

    await deleteKnowledgeBase(knowledgeBaseId);
    infoMessage.value = "知识库已删除。";

    if (selectedKnowledgeBaseId.value === knowledgeBaseId) {
      selectedKnowledgeBaseId.value = "";
      selectedDocumentId.value = null;
      documents.value = [];
      chunks.value = [];
      ingestionTaskNodes.value = [];
    }

    await load();
    if (!selectedKnowledgeBaseId.value) {
      selectedKnowledgeBaseId.value = knowledgeBases.value[0]?.id ?? "";
    }
  };

  const selectKnowledgeBase = (knowledgeBaseId: string) => {
    selectedKnowledgeBaseId.value = knowledgeBaseId;
  };

  const selectDocument = (documentId: number) => {
    selectedDocumentId.value = documentId;
  };

  const removeDocument = async (documentId: number) => {
    if (!canManageKnowledge.value) {
      denyManagementAction();
      return;
    }

    if (!selectedKnowledgeBaseId.value) {
      return;
    }

    await deleteKnowledgeDocument(selectedKnowledgeBaseId.value, documentId);
    infoMessage.value = "文档已删除。";
    if (selectedDocumentId.value === documentId) {
      selectedDocumentId.value = null;
      chunks.value = [];
      ingestionTaskNodes.value = [];
    }
    await refreshKnowledgeData();
  };

  const addDocument = async () => {
    if (!canManageKnowledge.value) {
      denyManagementAction();
      return;
    }

    if (!canCreateDocument.value) {
      return;
    }

    const created = await createKnowledgeDocument(
      selectedKnowledgeBaseId.value,
      documentTitle.value.trim(),
      documentContent.value.trim(),
      {
        documentType: documentType.value,
        chunkStrategy: chunkStrategy.value,
        chunkSize: chunkSize.value,
        chunkOverlap: chunkOverlap.value,
        recursiveSeparators: parseRecursiveSeparatorsText(recursiveSeparatorsText.value)
      }
    );

    documentTitle.value = "";
    documentContent.value = "";
    infoMessage.value = "文档已加入知识库。";
    await refreshKnowledgeData(created.id);
  };

  const uploadDocument = async (file: File | null) => {
    if (!canManageKnowledge.value) {
      denyManagementAction();
      return null;
    }

    if (!file || !selectedKnowledgeBaseId.value) {
      return null;
    }

    uploadLoading.value = true;
    error.value = "";
    infoMessage.value = "";
    uploadFileName.value = file.name;

    try {
      const created = await uploadKnowledgeDocument(selectedKnowledgeBaseId.value, file, {
        processMode: uploadProcessMode.value,
        pipelineId: uploadProcessMode.value === "data_channel" ? uploadPipelineId.value ?? undefined : undefined,
        documentType: "knowledge_base",
        chunkStrategy: uploadChunkStrategy.value,
        chunkSize: uploadChunkSize.value,
        chunkOverlap: uploadChunkOverlap.value,
        recursiveSeparators: parseRecursiveSeparatorsText(uploadRecursiveSeparatorsText.value),
        chunkConfig: buildChunkConfig(
          uploadChunkStrategy.value,
          uploadChunkSize.value,
          uploadChunkOverlap.value,
          uploadRecursiveSeparatorsText.value,
          uploadStructureMaxChars.value,
          uploadStructureMinChars.value
        )
      });
      infoMessage.value = "上传文档已完成入库。";
      await refreshKnowledgeData(created.id);
      return created;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "上传文档失败";
      return null;
    } finally {
      uploadLoading.value = false;
    }
  };

  const saveDocument = async (documentId: number, payload: KnowledgeDocumentUpdatePayload) => {
    if (!canManageKnowledge.value) {
      denyManagementAction();
      return null;
    }
    if (!selectedKnowledgeBaseId.value) {
      return null;
    }
    error.value = "";
    infoMessage.value = "";
    try {
      const updated = await updateKnowledgeDocument(selectedKnowledgeBaseId.value, documentId, payload);
      documents.value = documents.value.map((item) => (item.id === updated.id ? updated : item));
      if (payload.enabled !== undefined && selectedDocumentId.value === documentId) {
        await loadChunks(selectedKnowledgeBaseId.value, documentId);
      }
      infoMessage.value = "文档已更新。";
      return updated;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "更新文档失败";
      return null;
    }
  };

  const syncDocumentEditorDefaults = (strategy: string, options?: { chunkSize?: number; chunkOverlap?: number }) => {
    documentProcessMode.value = "chunk_strategy";
    documentChunkStrategy.value = strategy || "structure_aware";
    if (documentChunkStrategy.value === "structure_aware") {
      documentChunkSize.value = options?.chunkSize ?? DEFAULT_STRUCTURE_TARGET_CHARS;
      documentChunkOverlap.value = options?.chunkOverlap ?? 0;
      documentStructureMaxChars.value = DEFAULT_STRUCTURE_MAX_CHARS;
      documentStructureMinChars.value = DEFAULT_STRUCTURE_MIN_CHARS;
    } else {
      documentChunkSize.value = options?.chunkSize ?? DEFAULT_CHUNK_SIZE;
      documentChunkOverlap.value = options?.chunkOverlap ?? DEFAULT_CHUNK_OVERLAP;
    }
    documentRecursiveSeparatorsText.value = DEFAULT_RECURSIVE_SEPARATOR_TEXT;
  };

  const saveChunk = async (chunkId: number, payload: { content?: string; enabled?: boolean }) => {
    if (!canManageKnowledge.value) {
      denyManagementAction();
      return null;
    }
    if (!selectedKnowledgeBaseId.value || selectedDocumentId.value === null) {
      return null;
    }
    error.value = "";
    infoMessage.value = "";
    try {
      const updated = await updateKnowledgeChunk(selectedKnowledgeBaseId.value, selectedDocumentId.value, chunkId, payload);
      chunks.value = chunks.value.map((item) => (item.id === updated.id ? updated : item));
      infoMessage.value = "分块已更新。";
      return updated;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "更新分块失败";
      return null;
    }
  };

  const reindexDocument = async () => {
    if (!canManageKnowledge.value) {
      denyManagementAction();
      return;
    }

    if (!selectedKnowledgeBaseId.value || selectedDocumentId.value === null) {
      return;
    }

    reindexLoading.value = true;
    reindexingDocumentId.value = selectedDocumentId.value;
    error.value = "";
    infoMessage.value = "正在切块，请稍候...";

    try {
      const savedConfig = selectedDocument.value?.processing_config;
      const requestOptions = hasSavedProcessingConfig(savedConfig)
        ? normalizeSavedProcessingConfig(savedConfig)
        : {
            documentType: documentType.value,
            chunkStrategy: chunkStrategy.value,
            chunkSize: chunkSize.value,
            chunkOverlap: chunkOverlap.value,
            recursiveSeparators: parseRecursiveSeparatorsText(recursiveSeparatorsText.value)
          };
      const reindexed = await reindexKnowledgeDocument(selectedKnowledgeBaseId.value, selectedDocumentId.value, {
        ...requestOptions
      });
      await refreshKnowledgeData(reindexed.id);
      infoMessage.value = reindexed.vector_index_status === "indexed" ? "切块完成。" : "切块失败，请查看文档状态。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "切块失败";
      await refreshKnowledgeData(selectedDocumentId.value);
    } finally {
      reindexLoading.value = false;
      reindexingDocumentId.value = null;
    }
  };

  const reindexDocumentWithOptions = async (payload: {
    processMode?: "chunk_strategy" | "data_channel";
    pipelineId?: number;
    chunkStrategy: string;
    chunkSize: number;
    chunkOverlap: number;
    recursiveSeparatorsText: string;
    structureMaxChars?: number;
    structureMinChars?: number;
  }) => {
    if (!canManageKnowledge.value) {
      denyManagementAction();
      return null;
    }
    if (!selectedKnowledgeBaseId.value || selectedDocumentId.value === null) {
      return null;
    }
    reindexLoading.value = true;
    reindexingDocumentId.value = selectedDocumentId.value;
    error.value = "";
    infoMessage.value = "正在切块，请稍候...";
    try {
      const reindexed = await reindexKnowledgeDocument(selectedKnowledgeBaseId.value, selectedDocumentId.value, {
        documentType: "knowledge_base",
        processMode: payload.processMode ?? "chunk_strategy",
        pipelineId: payload.pipelineId,
        chunkStrategy: payload.chunkStrategy,
        chunkSize: payload.chunkSize,
        chunkOverlap: payload.chunkOverlap,
        recursiveSeparators: parseRecursiveSeparatorsText(payload.recursiveSeparatorsText),
        chunkConfig: buildChunkConfig(
          payload.chunkStrategy,
          payload.chunkSize,
          payload.chunkOverlap,
          payload.recursiveSeparatorsText,
          payload.structureMaxChars,
          payload.structureMinChars
        )
      });
      await refreshKnowledgeData(reindexed.id);
      infoMessage.value = reindexed.vector_index_status === "indexed" ? "切块完成。" : "切块失败，请查看文档状态。";
      return reindexed;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "切块失败";
      await refreshKnowledgeData(selectedDocumentId.value);
      return null;
    } finally {
      reindexLoading.value = false;
      reindexingDocumentId.value = null;
    }
  };

  watch(
    chunkSize,
    (value) => {
      const normalized = normalizeChunkSettings(value, chunkOverlap.value, chunkStrategy.value === "structure_aware" ? 5000 : 1000);
      if (normalized.chunkSize !== chunkSize.value) {
        chunkSize.value = normalized.chunkSize;
        return;
      }
      if (normalized.chunkOverlap !== chunkOverlap.value) {
        chunkOverlap.value = normalized.chunkOverlap;
      }
    },
    { immediate: true }
  );

  watch(
    uploadChunkSize,
    (value) => {
      const normalized = normalizeChunkSettings(value, uploadChunkOverlap.value, uploadChunkStrategy.value === "structure_aware" ? 5000 : 1000);
      if (normalized.chunkSize !== uploadChunkSize.value) {
        uploadChunkSize.value = normalized.chunkSize;
        return;
      }
      if (normalized.chunkOverlap !== uploadChunkOverlap.value) {
        uploadChunkOverlap.value = normalized.chunkOverlap;
      }
    },
    { immediate: true }
  );

  watch(chunkOverlap, (value) => {
    const normalized = normalizeChunkSettings(chunkSize.value, value, chunkStrategy.value === "structure_aware" ? 5000 : 1000);
    if (normalized.chunkOverlap !== chunkOverlap.value) {
      chunkOverlap.value = normalized.chunkOverlap;
    }
  });

  watch(uploadChunkOverlap, (value) => {
    const normalized = normalizeChunkSettings(uploadChunkSize.value, value, uploadChunkStrategy.value === "structure_aware" ? 5000 : 1000);
    if (normalized.chunkOverlap !== uploadChunkOverlap.value) {
      uploadChunkOverlap.value = normalized.chunkOverlap;
    }
  });

  watch([uploadProcessMode, ingestionPipelines], ([mode, pipelines]) => {
    if (mode === "data_channel" && uploadPipelineId.value === null) {
      uploadPipelineId.value = pipelines[0]?.id ?? null;
    }
  });

  watch(uploadChunkStrategy, (strategy) => {
    if (strategy === "structure_aware") {
      uploadChunkSize.value = DEFAULT_STRUCTURE_TARGET_CHARS;
      uploadChunkOverlap.value = 0;
      uploadStructureMaxChars.value = DEFAULT_STRUCTURE_MAX_CHARS;
      uploadStructureMinChars.value = DEFAULT_STRUCTURE_MIN_CHARS;
      return;
    }
    if (strategy === "fixed_size") {
      uploadChunkSize.value = DEFAULT_CHUNK_SIZE;
      uploadChunkOverlap.value = DEFAULT_CHUNK_OVERLAP;
    }
  });

  watch(documentChunkStrategy, (strategy) => {
    if (strategy === "structure_aware") {
      documentChunkSize.value = DEFAULT_STRUCTURE_TARGET_CHARS;
      documentChunkOverlap.value = 0;
      documentStructureMaxChars.value = DEFAULT_STRUCTURE_MAX_CHARS;
      documentStructureMinChars.value = DEFAULT_STRUCTURE_MIN_CHARS;
      return;
    }
    if (strategy === "fixed_size") {
      documentChunkSize.value = DEFAULT_CHUNK_SIZE;
      documentChunkOverlap.value = DEFAULT_CHUNK_OVERLAP;
    }
  });

  const routeProfileLoading = shallowRef(false);
  const routeProfile = ref<KnowledgeBaseRouteProfile | null>(null);

  const loadRouteProfile = async (knowledgeBaseId: string) => {
    if (!knowledgeBaseId) {
      routeProfile.value = null;
      return;
    }
    routeProfileLoading.value = true;
    try {
      const profile = await fetchRouteProfile(knowledgeBaseId);
      routeProfile.value = profile;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "加载意图路由配置失败";
    } finally {
      routeProfileLoading.value = false;
    }
  };

  const saveRouteProfile = async () => {
    if (!selectedKnowledgeBaseId.value || !routeProfile.value) return;
    routeProfileLoading.value = true;
    error.value = "";
    infoMessage.value = "";
    try {
      const updated = await updateRouteProfile(selectedKnowledgeBaseId.value, {
        profile_text: routeProfile.value.profile_text,
        sample_questions: routeProfile.value.sample_questions,
        keywords: routeProfile.value.keywords
      });
      routeProfile.value = updated;
      infoMessage.value = "意图路由配置已更新。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "保存意图路由配置失败";
    } finally {
      routeProfileLoading.value = false;
    }
  };

  const addKeyword = (keyword: string) => {
    if (!routeProfile.value || !keyword.trim()) return;
    const kw = keyword.trim();
    if (!routeProfile.value.keywords.includes(kw)) {
      routeProfile.value.keywords = [...routeProfile.value.keywords, kw];
    }
  };

  const removeKeyword = (index: number) => {
    if (!routeProfile.value) return;
    const arr = [...routeProfile.value.keywords];
    arr.splice(index, 1);
    routeProfile.value.keywords = arr;
  };

  const addSampleQuestion = (question: string) => {
    if (!routeProfile.value || !question.trim()) return;
    const q = question.trim();
    if (!routeProfile.value.sample_questions.includes(q)) {
      routeProfile.value.sample_questions = [...routeProfile.value.sample_questions, q];
    }
  };

  const removeSampleQuestion = (index: number) => {
    if (!routeProfile.value) return;
    const arr = [...routeProfile.value.sample_questions];
    arr.splice(index, 1);
    routeProfile.value.sample_questions = arr;
  };

  const changeUserRole = async (userId: string, role: string) => {
    if (!isAdmin.value) {
      denyManagementAction();
      return;
    }
    const updated = await updateAdminUserRole(userId, role);
    adminUsers.value = adminUsers.value.map((item) => (item.id === userId ? updated : item));
    infoMessage.value = "用户角色已更新。";
  };

  const saveUser = async (userId: string, payload: AdminUserUpdateRequest) => {
    if (!isAdmin.value) {
      denyManagementAction();
      return;
    }
    error.value = "";
    infoMessage.value = "";
    try {
      const updated = await updateAdminUser(userId, payload);
      adminUsers.value = adminUsers.value.map((item) => (item.id === userId ? updated : item));
      infoMessage.value = "用户已更新。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "更新用户失败";
    }
  };

  const removeUser = async (userId: string) => {
    if (!isAdmin.value) {
      denyManagementAction();
      return;
    }
    error.value = "";
    infoMessage.value = "";
    try {
      await deleteAdminUser(userId);
      adminUsers.value = adminUsers.value.filter((item) => item.id !== userId);
      infoMessage.value = "用户已删除。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "删除用户失败";
    }
  };

  const changeOwnPassword = async (payload: AdminUserPasswordChangeRequest) => {
    if (!isAdmin.value) {
      denyManagementAction();
      return;
    }
    error.value = "";
    infoMessage.value = "";
    try {
      await changeAdminUserPassword(payload);
      infoMessage.value = "密码已更新。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "修改密码失败";
    }
  };

  const createUser = async (payload: AdminUserCreateRequest) => {
    if (!isAdmin.value) {
      denyManagementAction();
      return;
    }
    error.value = "";
    infoMessage.value = "";
    try {
      const created = await createAdminUser(payload);
      adminUsers.value = [created, ...adminUsers.value.filter((item) => item.id !== created.id)];
      infoMessage.value = "用户已创建。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "新增用户失败";
    }
  };

  const loadDashboard = async (range = dashboardRange.value) => {
    if (!isAdmin.value) {
      adminDashboard.value = null;
      return;
    }
    dashboardRange.value = range;
    try {
      adminDashboard.value = await fetchAdminDashboard(range);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "加载 Dashboard 数据失败";
    }
  };

  const loadIntentTreeCacheStatus = async () => {
    if (!isAdmin.value) {
      adminIntentTreeCacheStatus.value = null;
      return;
    }
    try {
      adminIntentTreeCacheStatus.value = await fetchAdminIntentTreeCacheStatus();
    } catch (err) {
      adminIntentTreeCacheStatus.value = null;
      error.value = err instanceof Error ? err.message : "load intent tree cache status failed";
    }
  };

  const clearIntentTreeCache = async () => {
    if (!isAdmin.value) {
      denyManagementAction();
      return;
    }
    if (
      !adminIntentTreeCacheStatus.value?.enabled ||
      !adminIntentTreeCacheStatus.value.available ||
      !adminIntentTreeCacheStatus.value.exists
    ) {
      return;
    }
    try {
      adminIntentTreeCacheStatus.value = await clearAdminIntentTreeCache();
      infoMessage.value = "意图树缓存已清理。";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "清理意图树缓存失败";
    }
  };

  const createIntentNode = async (payload: AdminIntentNodeUpsertRequest) => {
    if (!isAdmin.value) {
      denyManagementAction();
      return null;
    }
    error.value = "";
    infoMessage.value = "";
    try {
      const created = await createAdminIntentNode(payload);
      adminIntentNodes.value = [...adminIntentNodes.value, created];
      await loadIntentTreeCacheStatus();
      infoMessage.value = "意图节点已创建。";
      return created;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "新增意图节点失败";
      return null;
    }
  };

  const updateIntentNode = async (nodeId: string, payload: AdminIntentNodeUpsertRequest) => {
    if (!isAdmin.value) {
      denyManagementAction();
      return null;
    }
    error.value = "";
    infoMessage.value = "";
    try {
      const updated = await updateAdminIntentNode(nodeId, payload);
      adminIntentNodes.value = adminIntentNodes.value.map((item) => (item.id === nodeId ? updated : item));
      await loadIntentTreeCacheStatus();
      infoMessage.value = "意图节点已更新。";
      return updated;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "更新意图节点失败";
      return null;
    }
  };

  const removeIntentNode = async (nodeId: string) => {
    if (!isAdmin.value) {
      denyManagementAction();
      return;
    }
    await deleteAdminIntentNode(nodeId);
    adminIntentNodes.value = adminIntentNodes.value.filter((item) => item.id !== nodeId);
    await loadIntentTreeCacheStatus();
    infoMessage.value = "意图节点已删除。";
  };

  const createKeywordMapping = async (payload: AdminKeywordMappingUpsertRequest) => {
    if (!isAdmin.value) {
      denyManagementAction();
      return null;
    }
    error.value = "";
    infoMessage.value = "";
    try {
      const created = await createAdminKeywordMapping(payload);
      adminKeywordMappings.value = [created, ...adminKeywordMappings.value];
      infoMessage.value = "关键词映射已创建。";
      return created;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "新增关键词映射失败";
      return null;
    }
  };

  const updateKeywordMapping = async (mappingId: string, payload: AdminKeywordMappingUpsertRequest) => {
    if (!isAdmin.value) {
      denyManagementAction();
      return null;
    }
    error.value = "";
    infoMessage.value = "";
    try {
      const updated = await updateAdminKeywordMapping(mappingId, payload);
      adminKeywordMappings.value = adminKeywordMappings.value.map((item) => (item.id === mappingId ? updated : item));
      infoMessage.value = "关键词映射已更新。";
      return updated;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "更新关键词映射失败";
      return null;
    }
  };

  const removeKeywordMapping = async (mappingId: string) => {
    if (!isAdmin.value) {
      denyManagementAction();
      return;
    }
    await deleteAdminKeywordMapping(mappingId);
    adminKeywordMappings.value = adminKeywordMappings.value.filter((item) => item.id !== mappingId);
    infoMessage.value = "关键词映射已删除。";
  };

  const loadTraceDetail = async (sessionId: string) => {
    if (!isAdmin.value || !sessionId) {
      selectedAdminTrace.value = null;
      selectedAdminTraceNodes.value = [];
      return;
    }
    error.value = "";
    try {
      const [detailData, nodeData] = await Promise.all([
        fetchAdminTraceDetail(sessionId),
        fetchAdminTraceNodes(sessionId)
      ]);
      selectedAdminTrace.value = detailData;
      selectedAdminTraceNodes.value = nodeData.items;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "加载链路详情失败";
    }
  };

  const clearTraceDetail = () => {
    selectedAdminTrace.value = null;
    selectedAdminTraceNodes.value = [];
  };

  watch(
    selectedKnowledgeBaseId,
    (knowledgeBaseId) => {
      void loadDocuments(knowledgeBaseId);
      void loadRouteProfile(knowledgeBaseId);
    },
    { immediate: true }
  );

  watch(
    [selectedKnowledgeBaseId, selectedDocumentId, canViewIngestion],
    ([knowledgeBaseId, documentId]) => {
      void loadChunks(knowledgeBaseId, documentId);
      void loadSelectedDocumentTask(documentId);
    },
    { immediate: true }
  );

  onMounted(() => {
    void load();
  });

  return {
    loading,
    documentLoading,
    chunkLoading,
    taskNodeLoading,
    uploadLoading,
    reindexLoading,
    reindexingDocumentId,
    error,
    infoMessage,
    meta,
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
    dashboardRange,
    adminIntentNodes,
    adminIntentTreeCacheStatus,
    adminKeywordMappings,
    adminTraces,
    adminTraceTotal,
    adminTracePage,
    adminTracePageSize,
    adminTraceId,
    selectedAdminTrace,
    selectedAdminTraceNodes,
    adminSettings,
    relatedTask,
    isAdmin,
    canManageKnowledge,
    canViewIngestion,
    readonlyNotice,
    documentTitle,
    documentContent,
    documentType,
    chunkStrategy,
    chunkSize,
    chunkOverlap,
    recursiveSeparatorsText,
    uploadFileName,
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
    manualChunkSummary: manualPresentation.chunkSummary,
    uploadChunkSummary: uploadPresentation.chunkSummary,
    manualShowChunkSizeControls: manualPresentation.showChunkSizeControls,
    uploadShowChunkSizeControls: uploadPresentation.showChunkSizeControls,
    manualShowRecursiveSeparatorControls: manualPresentation.showRecursiveSeparatorControls,
    uploadShowRecursiveSeparatorControls: uploadPresentation.showRecursiveSeparatorControls,
    manualShowSemanticNotice: manualPresentation.showSemanticNotice,
    uploadShowSemanticNotice: uploadPresentation.showSemanticNotice,
    manualAutoStrategyRecommendation: manualPresentation.autoStrategyRecommendation,
    uploadAutoStrategyRecommendation: uploadPresentation.autoStrategyRecommendation,
    manualRecursiveSeparatorSummary: manualPresentation.recursiveSeparatorSummary,
    uploadRecursiveSeparatorSummary: uploadPresentation.recursiveSeparatorSummary,
    canCreateDocument,
    canReindexDocument,
    addKnowledgeBase,
    saveKnowledgeBase,
    removeKnowledgeBase,
    selectKnowledgeBase,
    selectDocument,
    removeDocument,
    loadDocuments,
    loadAdminTraces,
    searchAdminTraces,
    loadChunks,
    createPipeline,
    updatePipeline,
    removePipeline,
    refreshKnowledgeData,
    addDocument,
    uploadDocument,
    saveDocument,
    saveChunk,
    syncDocumentEditorDefaults,
    reindexDocumentWithOptions,
    reindexDocument,
    loadSelectedDocumentTask,
    loadTaskNodes,
    routeProfileLoading,
    routeProfile,
    saveRouteProfile,
    addKeyword,
    removeKeyword,
    addSampleQuestion,
    removeSampleQuestion,
    changeUserRole,
    saveUser,
    removeUser,
    changeOwnPassword,
    createUser,
    loadDashboard,
    loadIntentTreeCacheStatus,
    clearIntentTreeCache,
    createIntentNode,
    updateIntentNode,
    removeIntentNode,
    createKeywordMapping,
    updateKeywordMapping,
    removeKeywordMapping,
    loadTraceDetail,
    clearTraceDetail
  };
}
