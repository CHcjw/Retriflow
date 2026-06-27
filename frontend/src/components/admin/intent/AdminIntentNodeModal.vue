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
const mcpToolId = defineModel<string>("mcpToolId", { required: true });
const description = defineModel<string>("description", { required: true });
const sampleQuestion = defineModel<string>("sampleQuestion", { required: true });
const ruleSnippet = defineModel<string>("ruleSnippet", { required: true });
const prompt = defineModel<string>("prompt", { required: true });
const paramPrompt = defineModel<string>("paramPrompt", { required: true });
const advanced = defineModel<string>("advanced", { required: true });
const topK = defineModel<number | null>("topK", { required: true });
const minScore = defineModel<number | null>("minScore", { required: true });
const sortOrder = defineModel<number>("sortOrder", { required: true });
const enabled = defineModel<boolean>("enabled", { required: true });

const emit = defineEmits<{
  close: [];
  save: [];
}>();
</script>

<template>
  <AdminModalShell
    aria-label="意图节点配置"
    description="配置意图树节点的路由类型、命中规则、提示词和检索参数。"
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
      <label v-if="nodeType !== 'MCP'" class="modal-label">
        知识库
        <select v-model="knowledgeBaseId" class="ui-input modal-control">
          <option value="">不绑定知识库</option>
          <option v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">{{ kb.name }} ({{ kb.collection_name || kb.id }})</option>
        </select>
      </label>
      <label v-else class="modal-label">
        MCP 工具 ID
        <input v-model="mcpToolId" class="ui-input modal-control" type="text" placeholder="例如：sales_query" />
      </label>
      <details class="modal-details" open>
        <summary>描述与示例</summary>
        <label class="modal-label">
          描述
          <textarea v-model="description" class="ui-input" rows="3" placeholder="描述这个意图适合回答的问题、业务范围和命中条件"></textarea>
        </label>
        <label class="modal-label">
          示例问题
          <textarea v-model="sampleQuestion" class="ui-input" rows="3" placeholder="每行一个示例问题"></textarea>
        </label>
        <label class="modal-label">
          规则片段
          <textarea v-model="ruleSnippet" class="ui-input" rows="3" placeholder="用于关键词或规则命中的补充描述"></textarea>
        </label>
      </details>
      <details class="modal-details">
        <summary>Prompt 配置</summary>
        <label class="modal-label">
          回答 Prompt
          <textarea v-model="prompt" class="ui-input" rows="4" placeholder="可选，用于节点回答或系统交互提示"></textarea>
        </label>
        <label v-if="nodeType === 'MCP'" class="modal-label">
          MCP 参数提取 Prompt
          <textarea v-model="paramPrompt" class="ui-input" rows="4" placeholder="可选，用于提取 MCP 工具参数"></textarea>
        </label>
      </details>
      <details class="modal-details" open>
        <summary>检索与排序</summary>
        <div class="modal-field-grid">
          <label class="modal-label">
            TopK
            <input v-model.number="topK" class="ui-input modal-control" min="1" type="number" placeholder="默认 5" />
          </label>
          <label class="modal-label">
            MinScore
            <input v-model.number="minScore" class="ui-input modal-control" min="0" max="1" step="0.01" type="number" placeholder="留空使用默认" />
          </label>
        </div>
        <div class="modal-field-grid">
          <label class="modal-label">
            排序
            <input v-model.number="sortOrder" class="ui-input modal-control" type="number" />
          </label>
          <label class="modal-checkline">
            <input v-model="enabled" type="checkbox" />
            启用节点
          </label>
        </div>
      </details>
      <details class="modal-details">
        <summary>高级设置</summary>
        <textarea v-model="advanced" class="ui-input" rows="3" placeholder="预留 JSON，高级配置将随业务扩展接入"></textarea>
      </details>
    </div>
    <template #actions>
      <button class="ghost-btn" type="button" @click="emit('close')">取消</button>
      <button class="primary-btn" type="button" :disabled="!name.trim() || !canSave" @click="emit('save')">保存</button>
    </template>
  </AdminModalShell>
</template>

<style scoped>
.modal-checkline {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  color: #172033;
  font-weight: 700;
}
</style>
