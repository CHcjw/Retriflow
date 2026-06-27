<script setup lang="ts">
import type { AdminIntentNodeItem } from "../../../services/adminApi";
import type { KnowledgeBaseItem } from "../../../services/knowledgeApi";
import AdminModalShell from "../common/AdminModalShell.vue";

const props = defineProps<{
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
const collectionName = defineModel<string>("collectionName", { required: true });
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

function syncKnowledgeBaseCollection(event: Event) {
  const target = event.target as HTMLSelectElement;
  const selected = props.knowledgeBases.find((item) => item.id === target.value);
  knowledgeBaseId.value = target.value;
  if (selected?.collection_name) {
    collectionName.value = selected.collection_name;
  }
}
</script>

<template>
  <AdminModalShell
    aria-label="意图节点配置"
    description="配置意图树节点的路由类型、命中规则、提示词和检索参数。"
    size="wide"
    :title="editingIntentNodeId ? '修改意图节点' : '新建意图节点'"
    @close="emit('close')"
  >
    <div class="intent-node-form">
      <section class="intent-section">
        <div class="intent-section-grid">
          <label class="modal-label">
            节点名称
            <input v-model="name" class="ui-input modal-control" type="text" placeholder="例如：销售数据" />
          </label>
          <label class="modal-label">
            意图标识
            <input v-model="code" class="ui-input modal-control" type="text" placeholder="例如：sales-data" />
          </label>
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
          <label class="modal-label wide">
            父节点
            <select v-model="parent" class="ui-input modal-control">
              <option value="ROOT">ROOT</option>
              <option v-for="item in adminIntentNodes" :key="item.id" :value="item.id">{{ item.name }}</option>
            </select>
          </label>
        </div>
      </section>

      <section v-if="nodeType !== 'MCP'" class="intent-section">
        <label class="modal-label">
          知识库
          <select :value="knowledgeBaseId" class="ui-input modal-control" @change="syncKnowledgeBaseCollection">
            <option value="">不绑定知识库</option>
            <option v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">
              {{ kb.name }} ({{ kb.collection_name || kb.id }})
            </option>
          </select>
        </label>
        <label class="modal-label">
          Collection
          <input v-model="collectionName" class="ui-input modal-control" type="text" placeholder="留空则使用知识库 collection" />
        </label>
      </section>

      <section v-else class="intent-section">
        <label class="modal-label">
          MCP 工具 ID
          <input v-model="mcpToolId" class="ui-input modal-control" type="text" placeholder="例如：sales_query" />
        </label>
      </section>

      <details class="modal-details intent-details" open>
        <summary>描述与示例</summary>
        <label class="modal-label">
          描述
          <textarea v-model="description" class="ui-input" rows="3" placeholder="节点的语义说明与说明场景"></textarea>
        </label>
        <label class="modal-label">
          示例问题
          <textarea v-model="sampleQuestion" class="ui-input" rows="3" placeholder="每行一个示例问题"></textarea>
        </label>
      </details>

      <details class="modal-details intent-details" open>
        <summary>Prompt 配置</summary>
        <label class="modal-label">
          短规则片段（可选）
          <textarea v-model="ruleSnippet" class="ui-input" rows="3" placeholder="多意图场景下的特定规则，会添加到整体提示词中"></textarea>
        </label>
        <label class="modal-label">
          Prompt模板（可选）
          <textarea v-model="prompt" class="ui-input" rows="4" placeholder="场景用的完整Prompt模板，KB和MCP节点都可配置"></textarea>
        </label>
        <label v-if="nodeType === 'MCP'" class="modal-label">
          MCP 参数提取 Prompt（可选）
          <textarea v-model="paramPrompt" class="ui-input" rows="4" placeholder="用于提取 MCP 工具参数"></textarea>
        </label>
      </details>

      <details class="modal-details intent-details" open>
        <summary>高级设置</summary>
        <div class="intent-section-grid">
          <label class="modal-label">
            节点 TopK（可选）
            <input v-model.number="topK" class="ui-input modal-control" min="1" type="number" placeholder="留空则使用全局 TopK" />
          </label>
          <label class="modal-label">
            MinScore（可选）
            <input v-model.number="minScore" class="ui-input modal-control" min="0" max="1" step="0.01" type="number" placeholder="留空则使用默认阈值" />
          </label>
          <label class="modal-label">
            排序
            <input v-model.number="sortOrder" class="ui-input modal-control" type="number" />
          </label>
          <label class="modal-checkline">
            <input v-model="enabled" type="checkbox" />
            启用节点
          </label>
        </div>
        <label class="modal-label advanced-json">
          扩展配置（JSON，可选）
          <textarea v-model="advanced" class="ui-input" rows="3" placeholder="预留 JSON，高级配置将随业务扩展接入"></textarea>
        </label>
      </details>
    </div>

    <template #actions>
      <button class="ghost-btn" type="button" @click="emit('close')">取消</button>
      <button class="primary-btn" type="button" :disabled="!name.trim() || !canSave" @click="emit('save')">保存</button>
    </template>
  </AdminModalShell>
</template>

<style scoped>
.intent-node-form {
  display: grid;
  gap: 18px;
  min-height: 0;
  overflow: auto;
  padding-right: 4px;
}

.intent-section,
.intent-details {
  display: grid;
  gap: 16px;
}

.intent-section-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px 22px;
}

.wide,
.advanced-json {
  grid-column: 1 / -1;
}

.intent-details textarea {
  min-height: 100px;
  resize: vertical;
}

.modal-checkline {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 54px;
  color: #172033;
  font-weight: 700;
}

.modal-checkline input {
  width: 18px;
  height: 18px;
  accent-color: var(--primary);
}

@media (max-width: 760px) {
  .intent-section-grid {
    grid-template-columns: 1fr;
  }
}
</style>
