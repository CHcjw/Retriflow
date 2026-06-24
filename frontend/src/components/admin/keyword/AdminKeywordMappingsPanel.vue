<script setup lang="ts">
import AdminTablePagination from "../common/AdminTablePagination.vue";

type KeywordRow = {
  id: string;
  raw: string;
  target: string;
  matchType: string;
  priority: number;
  enabled: boolean;
  status: string;
  remark: string;
  updatedAt: string;
};

const keywordSearch = defineModel<string>("keywordSearch", { required: true });
const keywordPage = defineModel<number>("keywordPage", { required: true });

defineProps<{
  canSave: boolean;
  pageSize: number;
  rows: KeywordRow[];
  total: number;
}>();

const emit = defineEmits<{
  create: [];
  delete: [mappingId: string];
  edit: [mappingId: string];
  save: [];
}>();

function formatDate(value: string) {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").slice(0, 19);
}
</script>

<template>
  <div class="page-head">
    <div>
      <h1>关键词映射</h1>
      <p>维护知识库命中的关键词，和意图识别共同决定检索范围。</p>
    </div>
    <button class="primary-btn" type="button" :disabled="!canSave" @click="emit('save')">
      保存关键词
    </button>
  </div>

  <section class="table-card">
    <div class="table-toolbar">
      <div>
        <h2>关键词映射管理</h2>
        <p>配置查询归一化的关键词映射规则。</p>
      </div>
      <div class="toolbar-actions">
        <input v-model="keywordSearch" class="ui-input" type="text" placeholder="搜索原始词/目标词" />
        <button class="ghost-btn" type="button" @click="emit('create')">新增映射</button>
      </div>
    </div>
    <div class="table-scroll">
      <table class="data-table mapping-table">
        <thead>
          <tr>
            <th>原始词</th>
            <th>目标词</th>
            <th>匹配类型</th>
            <th>优先级</th>
            <th>状态</th>
            <th>备注</th>
            <th>更新时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in rows" :key="item.id">
            <td class="text-ellipsis" :title="item.raw">{{ item.raw }}</td>
            <td class="text-ellipsis" :title="item.target">{{ item.target }}</td>
            <td>{{ item.matchType }}</td>
            <td>{{ item.priority }}</td>
            <td><span class="status-pill" :class="{ success: item.enabled, warning: !item.enabled }">{{ item.status }}</span></td>
            <td class="text-ellipsis" :title="item.remark">{{ item.remark }}</td>
            <td>{{ formatDate(item.updatedAt) }}</td>
            <td class="table-actions-cell">
              <button class="ghost-btn compact" type="button" @click="emit('edit', item.id)">修改</button>
              <button class="danger-btn compact" type="button" @click="emit('delete', item.id)">删除</button>
            </td>
          </tr>
          <tr v-if="total === 0">
            <td colspan="8" class="empty-cell">暂无关键词映射。</td>
          </tr>
        </tbody>
      </table>
    </div>
    <AdminTablePagination :page="keywordPage" :page-size="pageSize" :total="total" @change="keywordPage = $event" />
  </section>
</template>

<style scoped>
.text-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-actions-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
}
</style>
