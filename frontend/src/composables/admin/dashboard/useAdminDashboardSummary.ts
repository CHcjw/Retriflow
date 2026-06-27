import { computed, type Ref } from "vue";

import type { KnowledgeBaseItem, KnowledgeDocumentItem } from "../../../services/knowledgeApi";

export function useAdminDashboardSummary(
  knowledgeBases: Ref<KnowledgeBaseItem[]>,
  documents: Ref<KnowledgeDocumentItem[]>
) {
  const dashboardStats = computed(() => ({
    knowledgeBaseCount: knowledgeBases.value.length,
    documentCount: knowledgeBases.value.reduce((sum, item) => sum + item.document_count, 0),
    indexedDocumentCount: documents.value.filter((item) => item.vector_index_status === "indexed").length,
    chunkCount: documents.value.reduce((sum, item) => sum + item.vector_chunk_count, 0)
  }));

  return {
    dashboardStats
  };
}
