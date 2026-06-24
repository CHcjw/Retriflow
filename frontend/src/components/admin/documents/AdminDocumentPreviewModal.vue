<script setup lang="ts">
import type { KnowledgeDocumentPreviewResponse } from "../../../services/knowledgeApi";
import AdminModalShell from "../common/AdminModalShell.vue";

defineProps<{
  documentPreview: KnowledgeDocumentPreviewResponse | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  close: [];
}>();
</script>

<template>
  <AdminModalShell
    aria-label="文档预览"
    :description="documentPreview?.source_uri || '正在加载文档内容'"
    size="tall"
    :title="documentPreview?.title || '文档预览'"
    @close="emit('close')"
  >
    <div class="document-preview-box">
      <p v-if="loading" class="empty-cell">正在加载预览...</p>
      <pre v-else>{{ documentPreview?.content || "暂无可预览内容" }}</pre>
    </div>
    <template #actions>
      <button class="ghost-btn" type="button" @click="emit('close')">关闭</button>
    </template>
  </AdminModalShell>
</template>
