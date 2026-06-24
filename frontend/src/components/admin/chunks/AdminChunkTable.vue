<script setup lang="ts">
import type { KnowledgeChunkItem } from "../../../services/knowledgeApi";
import AdminTablePagination from "../common/AdminTablePagination.vue";

const props = defineProps<{
  allVisibleSelected: boolean;
  chunkLoading: boolean;
  chunkMetadataSummary: (metadata: Record<string, unknown>) => string;
  items: KnowledgeChunkItem[];
  page: number;
  pageSize: number;
  selectedChunkIds: number[];
  total: number;
}>();

const emit = defineEmits<{
  delete: [chunkId: number];
  edit: [chunkId: number];
  pageChange: [page: number];
  toggleVisibleSelection: [event: Event];
  "update:selectedChunkIds": [ids: number[]];
  updateEnabled: [chunkId: number, enabled: boolean];
}>();

function formatDate(value: string) {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").slice(0, 19);
}

function updateChunkSelection(chunkId: number, event: Event) {
  const checked = (event.target as HTMLInputElement | null)?.checked ?? false;
  const nextIds = checked
    ? Array.from(new Set([...props.selectedChunkIds, chunkId]))
    : props.selectedChunkIds.filter((id) => id !== chunkId);
  emit("update:selectedChunkIds", nextIds);
}
</script>

<template>
  <section class="table-card">
    <div class="table-toolbar">
      <div>
        <h2>Chunk 列表</h2>
        <p>展示当前文档真实入库的切块内容与元数据。</p>
      </div>
      <slot name="toolbar" />
    </div>

    <div class="table-scroll">
      <table class="data-table chunk-table">
        <thead>
          <tr>
            <th class="select-col">
              <input :checked="allVisibleSelected" type="checkbox" @change="emit('toggleVisibleSelection', $event)" />
            </th>
            <th>序号</th>
            <th>内容</th>
            <th>状态</th>
            <th>字符数</th>
            <th>策略</th>
            <th>元数据</th>
            <th>更新时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="chunk in items" :key="chunk.id">
            <td class="select-col">
              <input
                :checked="selectedChunkIds.includes(chunk.id)"
                type="checkbox"
                @change="updateChunkSelection(chunk.id, $event)"
              />
            </td>
            <td>{{ chunk.chunk_index }}</td>
            <td class="chunk-content"><span class="chunk-content-preview">{{ chunk.content }}</span></td>
            <td>
              <span class="status-pill" :class="{ success: chunk.enabled, warning: !chunk.enabled }">
                {{ chunk.enabled ? "启用" : "禁用" }}
              </span>
            </td>
            <td>{{ chunk.char_count }}</td>
            <td>{{ chunk.strategy }}</td>
            <td>{{ chunkMetadataSummary(chunk.metadata) }}</td>
            <td>{{ formatDate(chunk.created_at) }}</td>
            <td class="row-actions">
              <button class="ghost-btn compact" type="button" @click="emit('edit', chunk.id)">修改</button>
              <button class="ghost-btn compact" type="button" @click="emit('updateEnabled', chunk.id, !chunk.enabled)">
                {{ chunk.enabled ? "禁用" : "启用" }}
              </button>
              <button class="danger-btn compact" type="button" @click="emit('delete', chunk.id)">删除</button>
            </td>
          </tr>
          <tr v-if="!chunkLoading && total === 0">
            <td colspan="9" class="empty-cell">暂无分块，点击文档列表里的“切块”。</td>
          </tr>
        </tbody>
      </table>
    </div>
    <AdminTablePagination :page="page" :page-size="pageSize" :total="total" @change="emit('pageChange', $event)" />
  </section>
</template>
