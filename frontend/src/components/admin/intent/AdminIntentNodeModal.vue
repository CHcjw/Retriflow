<script setup lang="ts">
import type { AdminIntentNodeItem } from "../../../services/adminApi";
import type { KnowledgeBaseItem } from "../../../services/knowledgeApi";
import AdminModalShell from "../common/AdminModalShell.vue";

defineProps<{
  adminIntentNodes: AdminIntentNodeItem[];
  canSave: boolean;
  editingIntentNodeId: string;
  knowledgeBases: KnowledgeBaseItem[];
}>();

const name = defineModel<string>("name", { required: true });
const code = defineModel<string>("code", { required: true });
const level = defineModel<string>("level", { required: true });
const nodeType = defineModel<string>("nodeType", { required: true });
const parent = defineModel<string>("parent", { required: true });
const knowledgeBaseId = defineModel<string>("knowledgeBaseId", { required: true });
const description = defineModel<string>("description", { required: true });
const sampleQuestion = defineModel<string>("sampleQuestion", { required: true });
const prompt = defineModel<string>("prompt", { required: true });
const advanced = defineModel<string>("advanced", { required: true });

const emit = defineEmits<{
  close: [];
  save: [];
}>();
</script>

<template>
  <AdminModalShell
    aria-label="新建意图节点"
    description="当前后端使用知识库 Route Profile 承载意图描述、关键词和示例问题。"
    size="tall"
    :title="editingIntentNodeId ? '修改意图节点' : '新建意图节点'"
    @close="emit('close')"
  >
    <div class="modal-form single">
      <div class="modal-field-grid">
        <label class="modal-label">
          节点名称
          <input v-model="name" class="ui-input modal-control" type="text" placeholder="例如：OA 系统" />
        </label>
        <label class="modal-label">
          意图标识
          <input v-model="code" class="ui-input modal-control" type="text" placeholder="例如：biz-oa" />
        </label>
      </div>
      <div class="modal-field-grid">
        <label class="modal-label">
          层级
          <select v-model="level" class="ui-input modal-control">
            <option value="DOMAIN">DOMAIN - 顶层领域</option>
            <option value="CATEGORY">CATEGORY - 分类节点</option>
          </select>
        </label>
        <label class="modal-label">
          类型
          <select v-model="nodeType" class="ui-input modal-control">
            <option value="KB">KB - 知识库检索</option>
            <option value="MCP">MCP - 工具调用</option>
            <option value="SYSTEM">SYSTEM - 系统交互</option>
          </select>
        </label>
      </div>
      <label class="modal-label">
        父节点
        <select v-model="parent" class="ui-input modal-control">
          <option value="ROOT">ROOT</option>
          <option v-for="item in adminIntentNodes" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
      </label>
      <label class="modal-label">
        知识库
        <select v-model="knowledgeBaseId" class="ui-input modal-control">
          <option v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">{{ kb.name }} ({{ kb.id }})</option>
        </select>
      </label>
      <details class="modal-details" open>
        <summary>描述与示例</summary>
        <label class="modal-label">
          描述
          <textarea v-model="description" class="ui-input" rows="3" placeholder="描述这个意图适合回答的问题、业务范围和命中条件"></textarea>
        </label>
        <label class="modal-label">
          示例问题
          <input v-model="sampleQuestion" class="ui-input modal-control" type="text" placeholder="例如：OA 审批流程怎么配置？" />
        </label>
      </details>
      <details class="modal-details">
        <summary>Prompt 配置</summary>
        <textarea v-model="prompt" class="ui-input" rows="4" placeholder="可选，当前后端暂未独立持久化 prompt"></textarea>
      </details>
      <details class="modal-details">
        <summary>高级设置</summary>
        <textarea v-model="advanced" class="ui-input" rows="3" placeholder="可选 JSON，当前后端暂未独立持久化"></textarea>
      </details>
    </div>
    <template #actions>
      <button class="ghost-btn" type="button" @click="emit('close')">取消</button>
      <button class="primary-btn" type="button" :disabled="!name.trim() || !canSave" @click="emit('save')">保存</button>
    </template>
  </AdminModalShell>
</template>
