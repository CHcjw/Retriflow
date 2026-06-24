<script setup lang="ts">
import { computed, reactive, shallowRef, watch } from "vue";

import type { AdminSampleQuestionItem, AdminSampleQuestionUpsertRequest } from "../../../services/adminApi";
import AdminFormField from "../common/AdminFormField.vue";
import AdminModalShell from "../common/AdminModalShell.vue";
import AdminNotice from "../common/AdminNotice.vue";
import AdminTablePagination from "../common/AdminTablePagination.vue";

const props = defineProps<{
  clearError: () => void;
  createItem: (payload: AdminSampleQuestionUpsertRequest) => Promise<void>;
  deleteItem: (sampleId: string) => Promise<void>;
  items: AdminSampleQuestionItem[];
  error: string;
  refresh: () => Promise<void> | void;
  updateItem: (sampleId: string, payload: AdminSampleQuestionUpsertRequest) => Promise<void>;
}>();

type SampleQuestionRow = AdminSampleQuestionItem;

const tablePageSize = 10;
const search = shallowRef("");
const page = shallowRef(1);
const modalOpen = shallowRef(false);
const saving = shallowRef(false);
const editingId = shallowRef("");
const localError = shallowRef("");
const form = reactive({
  title: "",
  description: "",
  question: "",
  sort_order: 0,
  enabled: true
});

const rows = computed<SampleQuestionRow[]>(() => {
  const query = search.value.trim().toLowerCase();
  return props.items.filter((item) => {
    if (!query) {
      return true;
    }
    return [item.title, item.description, item.question].some((value) => value.toLowerCase().includes(query));
  });
});

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * tablePageSize;
  return rows.value.slice(start, start + tablePageSize);
});

const totalPageCount = computed(() => Math.max(1, Math.ceil(rows.value.length / tablePageSize)));
const currentPage = computed(() => Math.min(Math.max(1, page.value), totalPageCount.value));
const modalTitle = computed(() => (editingId.value ? "修改示例问题" : "新增示例问题"));

watch(search, () => {
  page.value = 1;
});

watch(rows, () => {
  if (page.value > totalPageCount.value) {
    page.value = totalPageCount.value;
  }
});

function openCreateModal() {
  editingId.value = "";
  Object.assign(form, {
    title: "",
    description: "",
    question: "",
    sort_order: props.items.length * 10 + 10,
    enabled: true
  });
  localError.value = "";
  props.clearError();
  modalOpen.value = true;
}

function openEditModal(item: AdminSampleQuestionItem) {
  editingId.value = item.id;
  Object.assign(form, {
    title: item.title,
    description: item.description,
    question: item.question,
    sort_order: item.sort_order,
    enabled: item.enabled
  });
  localError.value = "";
  props.clearError();
  modalOpen.value = true;
}

function closeModal() {
  modalOpen.value = false;
  localError.value = "";
}

async function submitForm() {
  const payload = {
    title: form.title.trim() || "示例问题",
    description: form.description.trim(),
    question: form.question.trim(),
    sort_order: Number(form.sort_order) || 0,
    enabled: form.enabled
  };
  if (!payload.question) {
    localError.value = "请输入示例问题内容。";
    return;
  }
  const duplicate = props.items.find((item) => item.question.trim() === payload.question && item.id !== editingId.value);
  if (duplicate) {
    localError.value = `示例问题已存在：${duplicate.title || duplicate.question}`;
    return;
  }
  saving.value = true;
  localError.value = "";
  try {
    if (editingId.value) {
      await props.updateItem(editingId.value, payload);
    } else {
      await props.createItem(payload);
    }
    closeModal();
  } catch {
    localError.value = props.error || "保存示例问题失败。";
  } finally {
    saving.value = false;
  }
}

async function deleteItem(sampleId: string) {
  try {
    await props.deleteItem(sampleId);
  } catch {
    localError.value = props.error || "删除示例问题失败。";
  }
}

function refreshItems() {
  void props.refresh();
}

function formatDate(value: string) {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").slice(0, 19);
}

function changePage(nextPage: number) {
  page.value = nextPage;
}
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>示例问题管理</h1>
        <p>配置欢迎页的示例问题与推荐问法。</p>
      </div>
      <div class="page-actions">
        <input v-model="search" class="ui-input" type="text" placeholder="搜索标题/描述/问题" />
        <button class="ghost-btn" type="button" @click="refreshItems">刷新</button>
        <button class="ghost-btn" type="button" @click="openCreateModal">新增示例问题</button>
      </div>
    </div>

    <section class="table-card">
      <div class="table-toolbar">
        <div>
          <h2>示例问题</h2>
          <p>用于聊天首页推荐问法展示，和知识库配置相互独立。</p>
        </div>
      </div>
      <div class="table-scroll">
        <table class="data-table sample-table">
          <thead>
            <tr>
              <th>标题</th>
              <th>描述</th>
              <th>示例问题</th>
              <th>状态</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in pagedRows" :key="item.id">
              <td :title="item.title">{{ item.title }}</td>
              <td :title="item.description || '-'">{{ item.description || "-" }}</td>
              <td :title="item.question">{{ item.question }}</td>
              <td><span class="status-pill" :class="item.enabled ? 'success' : 'muted'">{{ item.enabled ? "启用" : "禁用" }}</span></td>
              <td>{{ formatDate(item.updated_at) }}</td>
              <td>
                <div class="row-actions">
                  <button class="ghost-btn compact" type="button" @click="openEditModal(item)">修改</button>
                  <button class="danger-btn compact" type="button" @click="deleteItem(item.id)">删除</button>
                </div>
              </td>
            </tr>
            <tr v-if="rows.length === 0">
              <td colspan="6" class="empty-cell">暂无示例问题。</td>
            </tr>
          </tbody>
        </table>
      </div>
      <AdminTablePagination :page="currentPage" :page-size="tablePageSize" :total="rows.length" @change="changePage" />
    </section>

    <div v-if="modalOpen" class="modal-backdrop" @click.self="closeModal">
      <AdminModalShell aria-label="示例问题" description="配置聊天欢迎页展示的推荐问法。" :title="modalTitle" @close="closeModal">
        <div class="modal-form single">
          <AdminNotice
            v-if="localError || error"
            tone="danger"
            :message="localError || error"
            dismissible
            @dismiss="localError ? (localError = '') : props.clearError()"
          />
          <AdminFormField label="标题">
            <input v-model="form.title" class="ui-input modal-control" type="text" placeholder="例如：关于助手" />
          </AdminFormField>
          <AdminFormField label="描述">
            <input v-model="form.description" class="ui-input modal-control" type="text" placeholder="例如：询问助手是做什么的、是谁、能做什么等" />
          </AdminFormField>
          <AdminFormField label="示例问题">
            <textarea v-model="form.question" class="ui-input" rows="5" placeholder="请输入示例问题内容"></textarea>
          </AdminFormField>
          <div class="modal-field-grid">
            <AdminFormField label="排序">
              <input v-model.number="form.sort_order" class="ui-input modal-control" type="number" min="0" step="1" />
            </AdminFormField>
            <label class="modal-checkbox modal-checkbox-align">
              <input v-model="form.enabled" type="checkbox" />
              启用
            </label>
          </div>
        </div>
        <template #actions>
          <button class="ghost-btn" type="button" @click="closeModal">取消</button>
          <button class="primary-btn" type="button" :disabled="saving || !form.question.trim()" @click="submitForm">
            {{ saving ? "保存中..." : "保存" }}
          </button>
        </template>
      </AdminModalShell>
    </div>
  </div>
</template>

<style scoped>
.sample-table th:nth-child(1),
.sample-table td:nth-child(1) {
  width: 12%;
}

.sample-table th:nth-child(2),
.sample-table td:nth-child(2) {
  width: 20%;
}

.sample-table th:nth-child(3),
.sample-table td:nth-child(3) {
  width: 38%;
}

.sample-table th:nth-child(4),
.sample-table td:nth-child(4) {
  width: 8%;
}

.sample-table th:nth-child(5),
.sample-table td:nth-child(5) {
  width: 13%;
}

.sample-table th:nth-child(6),
.sample-table td:nth-child(6) {
  width: 9%;
}

.sample-table td:nth-child(1),
.sample-table td:nth-child(2),
.sample-table td:nth-child(3) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  word-break: keep-all;
  overflow-wrap: normal;
}

.row-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.modal-checkbox-align {
  align-self: end;
  min-height: 38px;
}

.status-pill.muted {
  background: #f1f5f9;
  color: #64748b;
}
</style>

