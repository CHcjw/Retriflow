import { computed, type Ref } from "vue";

import type { KnowledgeBaseItem } from "../../../services/knowledgeApi";

export function useAdminDashboardSummary(knowledgeBases: Ref<KnowledgeBaseItem[]>) {
  const dashboardStats = computed(() => ({
    knowledgeBaseCount: knowledgeBases.value.length,
    documentCount: knowledgeBases.value.reduce((sum, item) => sum + item.document_count, 0),
    indexedDocumentCount: knowledgeBases.value.reduce((sum, item) => sum + (item.indexed_document_count ?? 0), 0),
    chunkCount: knowledgeBases.value.reduce((sum, item) => sum + (item.chunk_count ?? 0), 0)
  }));

  return {
    dashboardStats
  };
}
