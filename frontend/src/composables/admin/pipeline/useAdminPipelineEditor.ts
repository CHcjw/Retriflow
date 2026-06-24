import { ref, shallowRef } from "vue";

import type { IngestionPipelineNodeConfig } from "../../services/pipelineApi";

export const pipelineNodeTypeOptions = [
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
] as const;

export function stringifyPipelineNodes(nodes: IngestionPipelineNodeConfig[]) {
  return JSON.stringify(nodes, null, 2);
}

function createDefaultPipelineNode(index: number): IngestionPipelineNodeConfig {
  return {
    node_id: `node-${index + 1}`,
    node_type: index === 0 ? "fetcher" : "custom",
    next_node_id: "",
    condition: "",
    config: {}
  };
}

export function useAdminPipelineEditor() {
  const showPipelineModal = shallowRef(false);
  const editingPipelineId = shallowRef<number | null>(null);
  const selectedPipelineNodes = ref<IngestionPipelineNodeConfig[]>([]);
  const selectedPipelineName = shallowRef("");
  const pipelineEditorMode = shallowRef<"form" | "json">("form");
  const newPipelineName = shallowRef("");
  const newPipelineDescription = shallowRef("");
  const pipelineJsonText = shallowRef("[]");
  const pipelineNodeDrafts = ref<IngestionPipelineNodeConfig[]>([]);

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
  }

  function closeCreatePipelineModal() {
    showPipelineModal.value = false;
    editingPipelineId.value = null;
  }

  function addPipelineNode() {
    pipelineNodeDrafts.value = [...pipelineNodeDrafts.value, createDefaultPipelineNode(pipelineNodeDrafts.value.length)];
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

  return {
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
    openPipelineNodesModal,
    removePipelineNode,
    syncPipelineFormFromJson,
    syncPipelineJsonFromForm,
    updatePipelineNodeConfigFromEvent
  };
}
