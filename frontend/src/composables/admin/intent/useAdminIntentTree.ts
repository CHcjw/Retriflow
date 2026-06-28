import { computed, shallowRef, type Ref } from "vue";

import type { AdminIntentNodeItem } from "../../../services/adminApi";
import type { KnowledgeBaseItem } from "../../../services/knowledgeApi";

export type AdminIntentRow = AdminIntentNodeItem & {
  type: string;
  path: string;
  resource: string;
  sampleCount: number;
  status: string;
};

export function useAdminIntentTree(options: {
  adminIntentNodes: Ref<AdminIntentNodeItem[]>;
  knowledgeBases: Ref<KnowledgeBaseItem[]>;
  pageSlice: <T>(items: T[], page: number) => T[];
}) {
  const intentSearch = shallowRef("");
  const intentMode = shallowRef<"list" | "tree">("tree");
  const selectedIntentNodeId = shallowRef("");
  const realIntentPage = shallowRef(1);

  const realIntentRows = computed(() => {
    const query = intentSearch.value.trim().toLowerCase();
    return options.adminIntentNodes.value
      .map((node) => {
        const kb = options.knowledgeBases.value.find((item) => item.id === node.knowledge_base_id);
        const parent = options.adminIntentNodes.value.find((item) => item.id === node.parent_id);
        const path = parent && parent.id !== "ROOT" ? `${parent.name} / ${node.name}` : node.name;
        const resource =
          node.node_type === "SYSTEM"
            ? "系统策略"
            : node.mcp_tool_id || node.collection_name || kb?.collection_name || node.knowledge_base_id || "-";
        return {
          ...node,
          type: node.node_type,
          path,
          resource,
          sampleCount: node.sample_questions.length,
          status: node.enabled ? "启用" : "停用"
        };
      })
      .filter((item) => {
        return (
          !query ||
          item.name.toLowerCase().includes(query) ||
          item.code.toLowerCase().includes(query) ||
          item.mcp_tool_id.toLowerCase().includes(query) ||
          item.collection_name.toLowerCase().includes(query) ||
          item.resource.toLowerCase().includes(query) ||
          item.id.toLowerCase().includes(query)
        );
      });
  });

  const pagedRealIntentRows = computed(() => options.pageSlice(realIntentRows.value, realIntentPage.value));

  const selectedIntentNode = computed(() =>
    options.adminIntentNodes.value.find((item) => item.id === selectedIntentNodeId.value) ?? options.adminIntentNodes.value[0] ?? null
  );

  const rootIntentNodes = computed(() =>
    options.adminIntentNodes.value
      .filter((node) => node.parent_id === "ROOT")
      .sort((left, right) => left.sort_order - right.sort_order)
  );

  function childIntentNodes(parentId: string) {
    return options.adminIntentNodes.value
      .filter((node) => node.parent_id === parentId)
      .sort((left, right) => left.sort_order - right.sort_order);
  }

  function intentNodeLevelClass(level: string) {
    return `level-${level.toLowerCase()}`;
  }

  function intentNodeTypeClass(type: string) {
    return `type-${type.toLowerCase()}`;
  }

  function selectIntentNode(nodeId: string) {
    selectedIntentNodeId.value = nodeId;
  }

  function selectFallbackIntentNode() {
    selectedIntentNodeId.value = options.adminIntentNodes.value[0]?.id ?? "";
  }

  return {
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
  };
}
