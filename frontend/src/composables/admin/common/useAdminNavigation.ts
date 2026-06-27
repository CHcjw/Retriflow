import { computed, shallowRef, type Ref } from "vue";

export type AdminTab =
  | "dashboard"
  | "knowledge"
  | "intent"
  | "keyword"
  | "pipeline"
  | "trace"
  | "users"
  | "sampleQuestions"
  | "settings";

export type KnowledgeStage = "chunks" | "documents" | "knowledge-bases";
export type PipelineTab = "pipelines" | "tasks";
export type AdminNavGroup = "main" | "settings";
export type AdminNavItem = { key: AdminTab; label: string; group: AdminNavGroup };
export type AdminPipelineNavItem = { key: PipelineTab; label: string; icon: string };

export function useAdminNavigation(options: {
  selectedKnowledgeBaseId: Ref<string>;
}) {
  const currentTab = shallowRef<AdminTab>("knowledge");
  const knowledgeStage = shallowRef<KnowledgeStage>("knowledge-bases");
  const sidebarCollapsed = shallowRef(false);
  const pipelineTab = shallowRef<PipelineTab>("pipelines");
  const pipelineMenuOpen = shallowRef(false);

  const navItems = computed<AdminNavItem[]>(() => [
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

  const pipelineNavItems: AdminPipelineNavItem[] = [
    { key: "pipelines", label: "流水线管理", icon: "▣" },
    { key: "tasks", label: "流水线任务", icon: "▤" }
  ];

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

  function activateTab(tab: AdminTab) {
    if (tab === "pipeline") {
      pipelineMenuOpen.value = !pipelineMenuOpen.value;
      return;
    }
    currentTab.value = tab;
    pipelineMenuOpen.value = false;
    if (tab === "knowledge" && !options.selectedKnowledgeBaseId.value) {
      knowledgeStage.value = "knowledge-bases";
    }
  }

  function activatePipelineTab(tab: PipelineTab) {
    currentTab.value = "pipeline";
    pipelineTab.value = tab;
    pipelineMenuOpen.value = true;
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value;
  }

  return {
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
  };
}
