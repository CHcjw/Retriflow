<script setup lang="ts">
import type { KnowledgeDocumentItem } from "../../../services/knowledgeApi";
import AdminTablePagination from "../common/AdminTablePagination.vue";

defineProps<{
  canManageKnowledge: boolean;
  documentLoading: boolean;
  documentTypeLabel: (type: string) => string;
  items: KnowledgeDocumentItem[];
  page: number;
  pageSize: number;
  processingModeLabel: (mode: string) => string;
  reindexingDocumentId: number | null;
  sourceLabel: (sourceType: string) => string;
  statusClass: (status: string) => string;
  statusLabel: (status: string) => string;
  total: number;
}>();

const emit = defineEmits<{
  delete: [documentId: number];
  edit: [documentId: number];
  openChunks: [documentId: number];
  pageChange: [page: number];
  preview: [documentId: number];
  reindex: [documentId: number];
}>();

function formatDate(value: string) {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").slice(0, 19);
}
</script>

<template>
  <section class="table-card">
    <div class="table-toolbar">
      <div>
        <h2>文档列表</h2>
        <p>上传后会解析为可预览文档，点击“切块”后再生成分块和向量索引。</p>
      </div>
      <slot name="toolbar" />
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
          <tr v-for="document in items" :key="document.id">
            <td>
              <button
                class="link-btn text-ellipsis"
                type="button"
                :disabled="document.vector_chunk_count <= 0"
                :title="document.title"
                @click="emit('openChunks', document.id)"
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
              <button class="ghost-btn compact" type="button" @click="emit('preview', document.id)">预览</button>
              <button
                class="ghost-btn compact"
                type="button"
                :disabled="document.vector_chunk_count <= 0"
                @click="emit('openChunks', document.id)"
              >
                分块详情
              </button>
              <button class="ghost-btn compact" type="button" @click="emit('edit', document.id)">修改</button>
              <button
                v-if="canManageKnowledge"
                class="ghost-btn compact"
                type="button"
                :disabled="reindexingDocumentId === document.id || document.vector_index_status === 'indexed'"
                @click="emit('reindex', document.id)"
              >
                {{ reindexingDocumentId === document.id ? "切块中..." : "切块" }}
              </button>
              <button v-if="canManageKnowledge" class="danger-btn compact" type="button" @click="emit('delete', document.id)">删除</button>
            </td>
          </tr>
          <tr v-if="!documentLoading && total === 0">
            <td colspan="9" class="empty-cell">暂无文档，请上传文档。</td>
          </tr>
        </tbody>
      </table>
    </div>
    <AdminTablePagination :page="page" :page-size="pageSize" :total="total" @change="emit('pageChange', $event)" />
  </section>
</template>

<style scoped>
.text-ellipsis {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: top;
  white-space: nowrap;
}
</style>
