<script setup lang="ts">
import type { IngestionPipelineNodeConfig } from "../../../services/pipelineApi";
import AdminModalShell from "../common/AdminModalShell.vue";

defineProps<{
  editingPipelineId: number | null;
  pipelineNodeTypeOptions: readonly string[];
}>();

const name = defineModel<string>("name", { required: true });
const description = defineModel<string>("description", { required: true });
const editorMode = defineModel<"form" | "json">("editorMode", { required: true });
const nodeDrafts = defineModel<IngestionPipelineNodeConfig[]>("nodeDrafts", { required: true });
const jsonText = defineModel<string>("jsonText", { required: true });

const emit = defineEmits<{
  addNode: [];
  close: [];
  removeNode: [index: number];
  save: [];
  syncForm: [];
  syncJson: [];
  updateNodeConfig: [index: number, event: Event];
}>();
</script>

<template>
  <AdminModalShell
    aria-label="新建流水线"
    :description="editingPipelineId === null ? '配置文档摄取、解析、切块、向量化等节点顺序，保存后会进入 RetriFlow 后端流水线定义表。' : '调整流水线名称、描述和节点配置。'"
    size="wide"
    :title="editingPipelineId === null ? '新建流水线' : '修改流水线'"
    @close="emit('close')"
  >

    <div class="modal-form">
      <label class="modal-label">
        流水线名称
        <input v-model="name" class="ui-input" type="text" placeholder="例如 retriflow-custom-ingestion" />
      </label>
      <label class="modal-label wide">
        描述
        <textarea v-model="description" class="ui-input" rows="3" placeholder="说明这条流水线负责什么场景"></textarea>
      </label>
    </div>

    <section class="pipeline-node-panel">
      <div class="node-panel-head">
        <div>
          <h3>节点配置</h3>
          <p>表单模式适合快速配置，JSON 模式适合复制已有流水线或批量调整。</p>
        </div>
        <div class="segmented-tabs">
          <button :class="{ active: editorMode === 'form' }" type="button" @click="emit('syncForm')">表单配置</button>
          <button :class="{ active: editorMode === 'json' }" type="button" @click="emit('syncJson')">JSON 配置</button>
        </div>
      </div>

      <template v-if="editorMode === 'form'">
        <div v-if="nodeDrafts.length === 0" class="empty-node-box">
          暂无节点，点击“添加节点”开始配置。
        </div>
        <article v-for="(node, index) in nodeDrafts" :key="`${node.node_id}-${index}`" class="pipeline-node-card">
          <div class="node-card-head">
            <div>
              <span class="status-pill">{{ node.node_type }}</span>
              <strong>节点 {{ index + 1 }}</strong>
            </div>
            <button class="danger-btn compact" type="button" @click="emit('removeNode', index)">删除</button>
          </div>
          <div class="pipeline-node-grid">
            <label class="modal-label">
              节点 ID
              <input v-model="node.node_id" class="ui-input" type="text" placeholder="parse" />
            </label>
            <label class="modal-label">
              节点类型
              <select v-model="node.node_type" class="ui-input">
                <option v-for="type in pipelineNodeTypeOptions" :key="type" :value="type">{{ type }}</option>
              </select>
            </label>
            <label class="modal-label">
              下一节点 ID
              <input v-model="node.next_node_id" class="ui-input" type="text" placeholder="chunk，可为空" />
            </label>
            <label class="modal-label">
              条件
              <input v-model="node.condition" class="ui-input" type="text" placeholder="例如 mime == application/pdf" />
            </label>
            <label class="modal-label wide">
              节点配置 JSON
              <textarea
                class="ui-input pipeline-json-mini"
                rows="4"
                :value="JSON.stringify(node.config, null, 2)"
                @input="emit('updateNodeConfig', index, $event)"
              ></textarea>
            </label>
          </div>
        </article>
        <button class="ghost-btn" type="button" @click="emit('addNode')">添加节点</button>
      </template>

      <template v-else>
        <textarea v-model="jsonText" class="ui-input pipeline-json-textarea" spellcheck="false"></textarea>
      </template>
    </section>

    <template #actions>
      <button class="ghost-btn" type="button" @click="emit('close')">取消</button>
      <button class="primary-btn" type="button" :disabled="!name.trim()" @click="emit('save')">{{ editingPipelineId === null ? "保存流水线" : "保存修改" }}</button>
    </template>
  </AdminModalShell>
</template>
