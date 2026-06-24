<script setup lang="ts">
import type { IngestionTaskItem } from "../../../services/knowledgeApi";
import type { IngestionPipelineNodeConfig } from "../../../services/pipelineApi";
import AdminTablePagination from "../common/AdminTablePagination.vue";

export type AdminPipelineRow = {
  id: number;
  name: string;
  description: string;
  nodeCount: number;
  owner: string;
  taskCount: number;
  updatedAt: string;
  nodes: IngestionPipelineNodeConfig[];
};

defineProps<{
  activeTab: "pipelines" | "tasks";
  pageSize: number;
  pipelinePage: number;
  pipelineRows: AdminPipelineRow[];
  pipelineTotal: number;
  taskPage: number;
  tasks: IngestionTaskItem[];
  taskTotal: number;
  sourceLabel: (sourceType: string) => string;
}>();

const emit = defineEmits<{
  deletePipeline: [pipelineId: number];
  editPipeline: [pipeline: AdminPipelineRow];
  pagePipeline: [page: number];
  pageTask: [page: number];
  viewPipelineNodes: [pipeline: AdminPipelineRow];
}>();

function formatDate(value: string) {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").slice(0, 19);
}
</script>

<template>
  <section v-if="activeTab === 'pipelines'" class="table-card">
    <div class="table-toolbar">
      <div>
        <h2>通道流水线</h2>
        <p>配置节点顺序与处理逻辑。</p>
      </div>
      <slot name="pipeline-toolbar" />
    </div>
    <div class="table-scroll">
      <table class="data-table pipeline-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>描述</th>
            <th>节点数</th>
            <th>负责人</th>
            <th>任务数</th>
            <th>更新时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="pipeline in pipelineRows" :key="pipeline.id">
            <td><strong class="text-ellipsis" :title="pipeline.name">{{ pipeline.name }}</strong></td>
            <td class="wide-cell">{{ pipeline.description }}</td>
            <td>{{ pipeline.nodeCount }}</td>
            <td>{{ pipeline.owner }}</td>
            <td>{{ pipeline.taskCount }}</td>
            <td>{{ formatDate(pipeline.updatedAt) }}</td>
            <td class="row-actions">
              <button class="ghost-btn compact" type="button" @click="emit('viewPipelineNodes', pipeline)">查看节点</button>
              <button class="ghost-btn compact" type="button" @click="emit('editPipeline', pipeline)">修改</button>
              <button class="danger-btn compact" type="button" @click="emit('deletePipeline', pipeline.id)">删除</button>
            </td>
          </tr>
          <tr v-if="pipelineRows.length === 0">
            <td colspan="7" class="empty-cell">暂无流水线，请点击“新增流水线”创建。</td>
          </tr>
        </tbody>
      </table>
    </div>
    <AdminTablePagination :page="pipelinePage" :page-size="pageSize" :total="pipelineTotal" @change="emit('pagePipeline', $event)" />
  </section>

  <section v-else class="table-card">
    <div class="table-toolbar">
      <div>
        <h2>通道任务</h2>
        <p>监控执行状态，共 {{ taskTotal }} 条任务。</p>
      </div>
      <slot name="task-toolbar" />
    </div>
    <div class="table-scroll">
      <table class="data-table pipeline-table pipeline-task-table">
        <thead>
          <tr>
            <th>任务 ID</th>
            <th>知识库</th>
            <th>文档</th>
            <th>来源</th>
            <th>状态</th>
            <th>分块数</th>
            <th>创建时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tasks" :key="task.id">
            <td>#{{ task.id }}</td>
            <td>{{ task.knowledge_base_id }}</td>
            <td>{{ task.document_id }}</td>
            <td>{{ sourceLabel(task.source_type) }}</td>
            <td>
              <span class="status-pill" :class="{ success: task.status === 'completed', danger: task.status === 'failed', warning: task.status !== 'completed' && task.status !== 'failed' }">
                {{ task.status }}
              </span>
            </td>
            <td>{{ task.chunk_count }}</td>
            <td>{{ formatDate(task.created_at) }}</td>
          </tr>
          <tr v-if="taskTotal === 0">
            <td colspan="7" class="empty-cell">暂无流水线任务。</td>
          </tr>
        </tbody>
      </table>
    </div>
    <AdminTablePagination :page="taskPage" :page-size="pageSize" :total="taskTotal" @change="emit('pageTask', $event)" />
  </section>
</template>

<style scoped>
.text-ellipsis {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: top;
  white-space: nowrap;
}
</style>
