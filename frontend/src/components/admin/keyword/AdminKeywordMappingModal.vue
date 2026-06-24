<script setup lang="ts">
import AdminModalShell from "../common/AdminModalShell.vue";

defineProps<{
  editingKeywordMappingId: string;
}>();

const rawKeyword = defineModel<string>("rawKeyword", { required: true });
const targetKeyword = defineModel<string>("targetKeyword", { required: true });
const matchType = defineModel<string>("matchType", { required: true });
const priority = defineModel<number>("priority", { required: true });
const enabled = defineModel<string>("enabled", { required: true });
const remark = defineModel<string>("remark", { required: true });

const emit = defineEmits<{
  close: [];
  save: [];
}>();
</script>

<template>
  <AdminModalShell
    aria-label="新增映射规则"
    description="配置查询归一化的关键词映射，保存到当前知识库路由关键词。"
    :title="editingKeywordMappingId ? '修改映射规则' : '新增映射规则'"
    @close="emit('close')"
  >
    <div class="modal-form single">
      <label class="modal-label">
        原始词 *
        <input v-model="rawKeyword" class="ui-input modal-control" type="text" placeholder="用户输入的原始关键词" />
      </label>
      <label class="modal-label">
        目标词 *
        <input v-model="targetKeyword" class="ui-input modal-control" type="text" placeholder="归一化后的目标关键词" />
        <span>当前后端保存原始关键词，目标词作为前端提示字段。</span>
      </label>
      <div class="modal-field-grid">
        <label class="modal-label">
          匹配类型
          <select v-model="matchType" class="ui-input modal-control">
            <option value="exact">精确匹配</option>
            <option value="contains">包含匹配</option>
            <option value="regex">正则匹配</option>
          </select>
        </label>
        <label class="modal-label">
          优先级
          <input v-model.number="priority" class="ui-input modal-control" type="number" />
        </label>
      </div>
      <label class="modal-label">
        启用状态
        <select v-model="enabled" class="ui-input modal-control">
          <option value="enabled">启用</option>
          <option value="disabled">停用</option>
        </select>
      </label>
      <label class="modal-label">
        备注
        <input v-model="remark" class="ui-input modal-control" type="text" placeholder="可选备注信息" />
      </label>
    </div>
    <template #actions>
      <button class="ghost-btn" type="button" @click="emit('close')">取消</button>
      <button class="primary-btn" type="button" :disabled="!rawKeyword.trim()" @click="emit('save')">保存</button>
    </template>
  </AdminModalShell>
</template>
