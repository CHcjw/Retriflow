<script setup lang="ts">
import type { IngestionPipelineNodeConfig } from "../../../services/pipelineApi";
import AdminModalShell from "../common/AdminModalShell.vue";

defineProps<{
  nodes: IngestionPipelineNodeConfig[];
  pipelineName: string;
}>();

const emit = defineEmits<{
  close: [];
}>();
</script>

<template>
  <AdminModalShell
    aria-label="查看流水线节点"
    :description="`${pipelineName}，共 ${nodes.length} 个节点。`"
    size="wide"
    title="查看节点"
    @close="emit('close')"
  >
    <section class="pipeline-node-panel readonly-node-panel">
      <article v-for="(node, index) in nodes" :key="`${node.node_id}-${index}`" class="pipeline-node-card">
        <div class="node-card-head">
          <div>
            <span class="status-pill">{{ node.node_type }}</span>
            <strong>{{ index + 1 }}. {{ node.node_id }}</strong>
          </div>
          <span class="muted-line">next: {{ node.next_node_id || "-" }}</span>
        </div>
        <dl class="node-detail-list">
          <dt>条件</dt>
          <dd>{{ node.condition || "-" }}</dd>
          <dt>配置</dt>
          <dd><pre>{{ JSON.stringify(node.config || {}, null, 2) }}</pre></dd>
        </dl>
      </article>
      <p v-if="nodes.length === 0" class="empty-cell">暂无节点。</p>
    </section>
    <template #actions>
      <button class="ghost-btn" type="button" @click="emit('close')">关闭</button>
    </template>
  </AdminModalShell>
</template>
