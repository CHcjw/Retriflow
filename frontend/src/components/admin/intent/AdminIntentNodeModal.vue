<script setup lang="ts">
import { reactive } from "vue";
import type { AdminIntentNodeItem } from "../../../services/adminApi";
import type { KnowledgeBaseItem } from "../../../services/knowledgeApi";
import AdminModalShell from "../common/AdminModalShell.vue";

type IntentPanelKey = "examples" | "prompt" | "advanced";

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

const openPanels = reactive<Record<IntentPanelKey, boolean>>({
  examples: false,
  prompt: false,
  advanced: false
});

const emit = defineEmits<{
  close: [];
  save: [];
}>();

function togglePanel(panel: IntentPanelKey) {
  openPanels[panel] = !openPanels[panel];
}

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
        <p class="intent-section-title">更新节点基础信息</p>
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
              <option value="CATEGORY">CATEGORY - 业务分类</option>
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
          <template v-if="nodeType !== 'MCP'">
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
              <input
                v-model="collectionName"
                class="ui-input modal-control"
                type="text"
                placeholder="留空则使用知识库 collection"
              />
            </label>
          </template>
          <label v-else class="modal-label wide">
            MCP 工具 ID
            <input v-model="mcpToolId" class="ui-input modal-control" type="text" placeholder="例如：sales_query" />
          </label>
        </div>
      </section>

      <section class="intent-accordion" :class="{ open: openPanels.examples }">
        <div
          class="intent-accordion-head"
          role="button"
          tabindex="0"
          :aria-expanded="openPanels.examples"
          @click="togglePanel('examples')"
          @keydown.enter.prevent="togglePanel('examples')"
          @keydown.space.prevent="togglePanel('examples')"
        >
          <span class="intent-accordion-arrow">{{ openPanels.examples ? "▾" : "▸" }}</span>
          <span class="intent-accordion-title">描述与示例</span>
        </div>
        <div v-show="openPanels.examples" class="intent-accordion-body">
          <label class="modal-label">
            描述
            <textarea v-model="description" class="ui-input" rows="3" placeholder="节点的语义说明与适用场景"></textarea>
          </label>
          <label class="modal-label">
            示例问题
            <textarea v-model="sampleQuestion" class="ui-input" rows="5" placeholder="每行一个示例问题"></textarea>
          </label>
        </div>
      </section>

      <section class="intent-accordion" :class="{ open: openPanels.prompt }">
        <div
          class="intent-accordion-head"
          role="button"
          tabindex="0"
          :aria-expanded="openPanels.prompt"
          @click="togglePanel('prompt')"
          @keydown.enter.prevent="togglePanel('prompt')"
          @keydown.space.prevent="togglePanel('prompt')"
        >
          <span class="intent-accordion-arrow">{{ openPanels.prompt ? "▾" : "▸" }}</span>
          <span class="intent-accordion-title">Prompt 配置</span>
        </div>
        <div v-show="openPanels.prompt" class="intent-accordion-body">
          <label class="modal-label">
            短规则片段（可选）
            <textarea
              v-model="ruleSnippet"
              class="ui-input"
              rows="3"
              placeholder="多意图场景下的特定规则，会添加到整体提示词中"
            ></textarea>
          </label>
          <label class="modal-label">
            Prompt模板（可选）
            <textarea
              v-model="prompt"
              class="ui-input"
              rows="4"
              placeholder="场景用的完整Prompt模板，KB和MCP节点都可配置"
            ></textarea>
          </label>
          <label v-if="nodeType === 'MCP'" class="modal-label">
            MCP 参数提取 Prompt（可选）
            <textarea v-model="paramPrompt" class="ui-input" rows="4" placeholder="用于提取 MCP 工具参数"></textarea>
          </label>
        </div>
      </section>

      <section class="intent-accordion" :class="{ open: openPanels.advanced }">
        <div
          class="intent-accordion-head"
          role="button"
          tabindex="0"
          :aria-expanded="openPanels.advanced"
          @click="togglePanel('advanced')"
          @keydown.enter.prevent="togglePanel('advanced')"
          @keydown.space.prevent="togglePanel('advanced')"
        >
          <span class="intent-accordion-arrow">{{ openPanels.advanced ? "▾" : "▸" }}</span>
          <span class="intent-accordion-title">高级设置</span>
        </div>
        <div v-show="openPanels.advanced" class="intent-accordion-body">
          <div class="intent-section-grid">
            <label class="modal-label">
              节点 TopK（可选）
              <input v-model.number="topK" class="ui-input modal-control" min="1" type="number" placeholder="留空则使用全局 TopK" />
            </label>
            <label class="modal-label">
              MinScore（可选）
              <input
                v-model.number="minScore"
                class="ui-input modal-control"
                min="0"
                max="1"
                step="0.01"
                type="number"
                placeholder="留空则使用默认阈值"
              />
            </label>
            <label class="modal-label">
              排序
              <input v-model.number="sortOrder" class="ui-input modal-control" type="number" />
            </label>
            <label class="modal-checkline">
              <input v-model="enabled" type="checkbox" />
              启用节点
            </label>
            <label class="modal-label advanced-json">
              扩展配置（JSON，可选）
              <textarea v-model="advanced" class="ui-input" rows="3" placeholder="预留 JSON，高级配置将随业务扩展接入"></textarea>
            </label>
          </div>
        </div>
      </section>
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
  align-content: start;
  gap: 9px;
  min-height: 0;
  padding-right: 4px;
  overscroll-behavior: contain;
}

.intent-section {
  display: grid;
  gap: 8px;
}

.intent-section-title {
  margin: 0;
  color: #64748b;
  font-size: 14px;
  font-weight: 700;
}

.intent-section-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px 14px;
}

.wide,
.advanced-json {
  grid-column: 1 / -1;
}

.intent-node-form :deep(.modal-control) {
  min-height: 40px;
  border-radius: 12px;
  padding-inline: 14px;
}

.intent-node-form :deep(.modal-label) {
  gap: 5px;
  font-size: 14px;
}

.intent-accordion {
  overflow: hidden;
  border: 1px solid var(--border-light);
  border-radius: 14px;
  background: #f7fafb;
}

.intent-accordion.open {
  background: #f8fbfd;
}

.intent-accordion-head {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 44px !important;
  gap: 8px;
  border: 0;
  padding: 0 18px;
  background: transparent;
  color: #172033 !important;
  font-size: 15px !important;
  line-height: 1.2 !important;
  font-weight: 800 !important;
  text-align: left;
  cursor: pointer;
  user-select: none;
}

.intent-accordion-head:focus-visible {
  outline: 2px solid rgba(15, 143, 130, 0.35);
  outline-offset: -2px;
}

.intent-accordion-arrow {
  display: inline-flex;
  width: 14px;
  justify-content: center;
  color: #172033 !important;
  font-size: 16px !important;
  line-height: 1;
}

.intent-accordion-title {
  display: inline-flex !important;
  align-items: center;
  min-height: 20px;
  color: #172033 !important;
  font-size: 15px !important;
  line-height: 1.2 !important;
  font-weight: 800 !important;
  white-space: nowrap;
}

.intent-accordion-body {
  display: grid;
  gap: 12px;
  padding: 0 18px 14px;
  border-top: 1px solid #e8eef7;
}

.intent-accordion-body textarea {
  min-height: 96px;
  resize: vertical;
}

.modal-checkline {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 48px;
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

@media (min-width: 761px) and (max-width: 1120px) {
  .intent-section-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
