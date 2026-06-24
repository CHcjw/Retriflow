import { shallowRef } from "vue";

import type { KnowledgeBaseItem, KnowledgeBaseUpsertOptions } from "../../../services/knowledgeApi";

const DEFAULT_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B";

export function useAdminKnowledgeBaseForm() {
  const editingKnowledgeBaseId = shallowRef("");
  const newKnowledgeBaseName = shallowRef("");
  const newKnowledgeEmbeddingModel = shallowRef(DEFAULT_EMBEDDING_MODEL);
  const newKnowledgeCollectionName = shallowRef("");

  function resetKnowledgeBaseForm() {
    editingKnowledgeBaseId.value = "";
    newKnowledgeBaseName.value = "";
    newKnowledgeEmbeddingModel.value = DEFAULT_EMBEDDING_MODEL;
    newKnowledgeCollectionName.value = "";
  }

  function fillKnowledgeBaseForm(knowledgeBase: KnowledgeBaseItem) {
    editingKnowledgeBaseId.value = knowledgeBase.id;
    newKnowledgeBaseName.value = knowledgeBase.name;
    newKnowledgeEmbeddingModel.value = knowledgeBase.embedding_model || DEFAULT_EMBEDDING_MODEL;
    newKnowledgeCollectionName.value = knowledgeBase.collection_name;
  }

  function buildKnowledgeBasePayload(): KnowledgeBaseUpsertOptions {
    return {
      name: newKnowledgeBaseName.value.trim(),
      embeddingModel: newKnowledgeEmbeddingModel.value,
      collectionName: newKnowledgeCollectionName.value.trim()
    };
  }

  return {
    editingKnowledgeBaseId,
    newKnowledgeBaseName,
    newKnowledgeEmbeddingModel,
    newKnowledgeCollectionName,
    resetKnowledgeBaseForm,
    fillKnowledgeBaseForm,
    buildKnowledgeBasePayload
  };
}
