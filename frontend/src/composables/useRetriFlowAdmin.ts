import { computed, onMounted, ref, shallowRef, watch } from "vue";

import {
  createAdminIntentNode,
  createAdminKeywordMapping,
  createKnowledgeBase,
  createAdminUser,
  createIngestionPipeline,
  createKnowledgeDocument,
  deleteAdminIntentNode,
  deleteAdminKeywordMapping,
  deleteKnowledgeBase,
  deleteKnowledgeDocument,
  fetchAdminDashboard,
  fetchAdminIntentNodes,
  fetchAdminKeywordMappings,
  fetchAdminTraceDetail,
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
  updateAdminUserRole,
  type AdminUserCreateRequest,
  type IngestionPipelineCreateRequest,
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

const DEFAULT_CHUNK_SIZE = 600;
const DEFAULT_CHUNK_OVERLAP = 120;
const DEFAULT_RECURSIVE_SEPARATOR_TEXT = ["\\n\\n", "\\n", "。", "！", "？", ". ", "! ", "? ", "[space]"].join("\n");

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
  { value: "auto", label: "自动策略" },
  { value: "fixed", label: "固定大小分块" },
  { value: "overlap", label: "重叠分块" },
  { value: "recursive", label: "递归分块" },
  { value: "semantic_embedding", label: "Embedding 语义分块" },
  { value: "hybrid_recursive_semantic", label: "递归 + 语义混合分块" }
] as const;

const autoStrategyRecommendations: Record<string, string> = {
  manual: "普通文本默认推荐递归分块，优先按段落和句子边界切分。",
  knowledge_base: "知识库文档默认推荐递归分块，兼顾章节结构和上下文连续性。",
  faq: "FAQ 默认推荐递归分块，便于保留问题与答案的成对关系。",
  contract: "合同 / 法律文本默认推荐 Embedding 语义分块，更适合按条款语义聚合。",
  log: "日志默认推荐固定大小分块，便于稳定切片和时序检索。",
  html: "HTML 页面默认推荐递归分块，优先保留标题层级和段落结构。",
  ocr: "OCR 文本默认推荐重叠分块，用重叠窗口缓解识别噪声造成的断句问题。",
  mixed_knowledge: "混合企业知识默认推荐递归 + 语义混合分块，先按结构粗切，再做语义细切。"
};

function normalizeChunkSettings(chunkSize: number, chunkOverlap: number) {
  const safeChunkSize = Number.isFinite(chunkSize)
    ? Math.max(200, Math.min(1000, Math.floor(chunkSize)))
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
    () =>
      `chunk size ${chunkSize.value} / overlap ${chunkOverlap.value}，建议 overlap 约为 chunk size 的 10% - 25%。`
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
  const ingestionTaskNodes = ref<Awaited<ReturnType<typeof fetchIngestionTaskNodes>>["items"]>([]);
  const adminUsers = ref<Awaited<ReturnType<typeof fetchAdminUsers>>["items"]>([]);
  const adminDashboard = ref<Awaited<ReturnType<typeof fetchAdminDashboard>> | null>(null);
  const dashboardRange = shallowRef("24h");
  const adminIntentNodes = ref<Awaited<ReturnType<typeof fetchAdminIntentNodes>>["items"]>([]);
  const adminKeywordMappings = ref<Awaited<ReturnType<typeof fetchAdminKeywordMappings>>["items"]>([]);
  const adminTraces = ref<Awaited<ReturnType<typeof fetchAdminTraces>>["items"]>([]);
  const selectedAdminTrace = ref<Awaited<ReturnType<typeof fetchAdminTraceDetail>> | null>(null);
  const adminSettings = ref<Awaited<ReturnType<typeof fetchAdminSettings>>["items"]>([]);

  const documentTitle = shallowRef("");
  const documentContent = shallowRef("");
  const documentType = shallowRef("manual");
  const chunkStrategy = shallowRef("auto");
  const chunkSize = shallowRef(DEFAULT_CHUNK_SIZE);
  const chunkOverlap = shallowRef(DEFAULT_CHUNK_OVERLAP);
  const recursiveSeparatorsText = shallowRef(DEFAULT_RECURSIVE_SEPARATOR_TEXT);

  const uploadFileName = shallowRef("");
  const uploadDocumentType = shallowRef("knowledge_base");
  const uploadChunkStrategy = shallowRef("auto");
  const uploadChunkSize = shallowRef(DEFAULT_CHUNK_SIZE);
  const uploadChunkOverlap = shallowRef(DEFAULT_CHUNK_OVERLAP);
  const uploadRecursiveSeparatorsText = shallowRef(DEFAULT_RECURSIVE_SEPARATOR_TEXT);

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
  const relatedTask = computed(() =>
    ingestionTasks.value.find((item) => item.document_id === selectedDocumentId.value) ?? null
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
    uploadDocumentType,
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
          keywordMappingData,
          traceData,
          settingData
        ] = await Promise.all([
          fetchIngestionPipelines(),
          fetchIngestionTasks(),
          fetchAdminUsers(),
          fetchAdminDashboard(dashboardRange.value),
          fetchAdminIntentNodes(),
          fetchAdminKeywordMappings(),
          fetchAdminTraces(),
          fetchAdminSettings()
        ]);
        ingestionPipelines.value = pipelineData.items;
        ingestionTasks.value = taskData.items;
        adminUsers.value = userData.items;
        adminDashboard.value = dashboardData;
        adminIntentNodes.value = intentNodeData.items;
        adminKeywordMappings.value = keywordMappingData.items;
        adminTraces.value = traceData.items;
        adminSettings.value = settingData.items;
      } else {
        ingestionPipelines.value = [];
        ingestionTasks.value = [];
        adminUsers.value = [];
        adminDashboard.value = null;
        adminIntentNodes.value = [];
        adminKeywordMappings.value = [];
        adminTraces.value = [];
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

  const addKnowledgeBase = async (name?: string) => {
    if (!canManageKnowledge.value) {
      denyManagementAction();
      return;
    }

    const created = await createKnowledgeBase(name?.trim() || `RetriFlow 知识库 ${knowledgeBases.value.length + 1}`);
    selectedKnowledgeBaseId.value = created.id;
    infoMessage.value = "知识库已创建。";
    await load();
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
      return;
    }

    if (!file || !selectedKnowledgeBaseId.value) {
      return;
    }

    uploadLoading.value = true;
    error.value = "";
    infoMessage.value = "";
    uploadFileName.value = file.name;

    try {
      const created = await uploadKnowledgeDocument(selectedKnowledgeBaseId.value, file, {
        documentType: uploadDocumentType.value,
        chunkStrategy: uploadChunkStrategy.value,
        chunkSize: uploadChunkSize.value,
        chunkOverlap: uploadChunkOverlap.value,
        recursiveSeparators: parseRecursiveSeparatorsText(uploadRecursiveSeparatorsText.value)
      });
      infoMessage.value = "上传文档已完成入库。";
      await refreshKnowledgeData(created.id);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "上传文档失败";
    } finally {
      uploadLoading.value = false;
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
    error.value = "";
    infoMessage.value = "";

    try {
      const reindexed = await reindexKnowledgeDocument(selectedKnowledgeBaseId.value, selectedDocumentId.value, {
        documentType: documentType.value,
        chunkStrategy: chunkStrategy.value,
        chunkSize: chunkSize.value,
        chunkOverlap: chunkOverlap.value,
        recursiveSeparators: parseRecursiveSeparatorsText(recursiveSeparatorsText.value)
      });
      infoMessage.value = "";
      await refreshKnowledgeData(reindexed.id);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "重建索引失败";
    } finally {
      reindexLoading.value = false;
    }
  };

  watch(
    chunkSize,
    (value) => {
      const normalized = normalizeChunkSettings(value, chunkOverlap.value);
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
      const normalized = normalizeChunkSettings(value, uploadChunkOverlap.value);
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
    const normalized = normalizeChunkSettings(chunkSize.value, value);
    if (normalized.chunkOverlap !== chunkOverlap.value) {
      chunkOverlap.value = normalized.chunkOverlap;
    }
  });

  watch(uploadChunkOverlap, (value) => {
    const normalized = normalizeChunkSettings(uploadChunkSize.value, value);
    if (normalized.chunkOverlap !== uploadChunkOverlap.value) {
      uploadChunkOverlap.value = normalized.chunkOverlap;
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
      return;
    }
    error.value = "";
    try {
      selectedAdminTrace.value = await fetchAdminTraceDetail(sessionId);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "加载链路详情失败";
    }
  };

  const clearTraceDetail = () => {
    selectedAdminTrace.value = null;
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
      const task = ingestionTasks.value.find((item) => item.document_id === documentId) ?? null;
      void loadTaskNodes(task?.id ?? null);
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
    ingestionTaskNodes,
    adminUsers,
    adminDashboard,
    dashboardRange,
    adminIntentNodes,
    adminKeywordMappings,
    adminTraces,
    selectedAdminTrace,
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
    uploadDocumentType,
    uploadChunkStrategy,
    uploadChunkSize,
    uploadChunkOverlap,
    uploadRecursiveSeparatorsText,
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
    removeKnowledgeBase,
    selectKnowledgeBase,
    selectDocument,
    removeDocument,
    loadDocuments,
    loadChunks,
    createPipeline,
    refreshKnowledgeData,
    addDocument,
    uploadDocument,
    reindexDocument,
    loadTaskNodes,
    routeProfileLoading,
    routeProfile,
    saveRouteProfile,
    addKeyword,
    removeKeyword,
    addSampleQuestion,
    removeSampleQuestion,
    changeUserRole,
    createUser,
    loadDashboard,
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
