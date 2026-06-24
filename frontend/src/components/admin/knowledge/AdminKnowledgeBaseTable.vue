<script setup lang="ts">
import type { KnowledgeBaseItem } from "../../../services/knowledgeApi";
import AdminTablePagination from "../common/AdminTablePagination.vue";

defineProps<{
  canManageKnowledge: boolean;
  items: KnowledgeBaseItem[];
  loading: boolean;
  page: number;
  pageSize: number;
  total: number;
}>();

const emit = defineEmits<{
  delete: [knowledgeBaseId: string];
  edit: [knowledgeBaseId: string];
  openDocuments: [knowledgeBaseId: string];
  pageChange: [page: number];
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
    <div class="table-scroll">
      <table class="data-table kb-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>Embedding 模型</th>
            <th>Collection</th>
            <th>文档数</th>
            <th>负责人</th>
            <th>创建时间</th>
            <th>修改时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="knowledgeBase in items" :key="knowledgeBase.id">
            <td>
              <button class="link-btn ellipsis-link" type="button" :title="knowledgeBase.name" @click="emit('openDocuments', knowledgeBase.id)">
                {{ knowledgeBase.name }}
              </button>
            </td>
            <td class="text-ellipsis" :title="knowledgeBase.embedding_model">{{ knowledgeBase.embedding_model }}</td>
            <td><span class="badge">{{ knowledgeBase.collection_name || knowledgeBase.id }}</span></td>
            <td>{{ knowledgeBase.document_count }}</td>
            <td>{{ knowledgeBase.owner || "admin" }}</td>
            <td>{{ formatDate(knowledgeBase.created_at) }}</td>
            <td>{{ formatDate(knowledgeBase.updated_at || knowledgeBase.created_at) }}</td>
            <td class="row-actions">
              <button class="ghost-btn compact" type="button" @click="emit('openDocuments', knowledgeBase.id)">文档</button>
              <button class="ghost-btn compact" type="button" @click="emit('edit', knowledgeBase.id)">修改</button>
              <button
                v-if="canManageKnowledge"
                class="danger-btn compact"
                type="button"
                @click="emit('delete', knowledgeBase.id)"
              >
                删除
              </button>
            </td>
          </tr>
          <tr v-if="!loading && total === 0">
            <td colspan="8" class="empty-cell">暂无知识库，先新建一个。</td>
          </tr>
        </tbody>
      </table>
    </div>
    <AdminTablePagination :page="page" :page-size="pageSize" :total="total" @change="emit('pageChange', $event)" />
  </section>
</template>

<style scoped>
.text-ellipsis,
.ellipsis-link {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: top;
  white-space: nowrap;
}
</style>
