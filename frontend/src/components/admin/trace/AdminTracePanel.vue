<script setup lang="ts">
import type { AdminTraceDetailResponse, AdminTraceNodeItem } from "../../../services/adminApi";
import AdminTablePagination from "../common/AdminTablePagination.vue";
import AdminTraceTreePanel from "./AdminTraceTreePanel.vue";

type TraceRow = {
  name: string;
  id: string;
  traceId: string;
  owner: string;
  messageCount: number;
  latestMessageId: number | string;
  duration: string;
  status: string;
  executedAt: string;
  title: string;
};

type TraceTimelineRow = {
  id: number;
  name: string;
  type: string;
  status: string;
  startedAt: string;
  duration: string;
  offset: number;
  width: number;
  content: string;
};

type TraceStats = {
  nodeCount: number;
  successCount: number;
  failedCount: number;
  userMessages: number;
  assistantMessages: number;
  totalDuration: string;
};

const traceId = defineModel<string>("traceId", { required: true });

defineProps<{
  adminTracePage: number;
  adminTracePageSize: number;
  adminTraceTotal: number;
  rows: TraceRow[];
  selectedAdminTrace: AdminTraceDetailResponse | null;
  selectedAdminTraceNodes: AdminTraceNodeItem[];
  selectedTraceRows: TraceTimelineRow[];
  selectedTraceStats: TraceStats;
  formatDuration: (durationMs: number) => string;
}>();

const emit = defineEmits<{
  back: [];
  loadDetail: [sessionId: string, traceId: string];
  pageChange: [page: number];
  refresh: [];
  refreshDetail: [sessionId: string, traceId: string];
  search: [];
}>();

function formatDate(value: string) {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").slice(0, 19);
}
</script>

<template>
  <template v-if="!selectedAdminTrace">
    <div class="page-head">
      <div>
        <h1>链路追踪</h1>
        <p>按 TraceID 检索运行记录，点击查看链路详情。</p>
      </div>
      <div class="page-actions">
        <input v-model="traceId" class="ui-input" inputmode="numeric" maxlength="20" type="text" placeholder="输入 20 位 TraceID" />
        <button class="ghost-btn" type="button" @click="emit('search')">搜索</button>
        <button class="ghost-btn" type="button" @click="emit('refresh')">刷新</button>
      </div>
    </div>

    <section class="table-card">
      <div class="table-scroll">
        <table class="data-table trace-table">
          <thead>
            <tr>
              <th>Trace Name</th>
              <th>Trace Id</th>
              <th>会话ID / TaskID</th>
              <th>用户名</th>
              <th>耗时</th>
              <th>状态</th>
              <th>执行时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="trace in rows" :key="trace.id">
              <td><strong>{{ trace.name }}</strong><p class="muted-line">{{ trace.title }}</p></td>
              <td>{{ trace.traceId }}</td>
              <td>{{ trace.id }} / {{ trace.latestMessageId }}</td>
              <td>{{ trace.owner }}</td>
              <td>{{ trace.duration }}</td>
              <td><span class="status-pill" :class="{ success: trace.status === 'SUCCESS', warning: trace.status !== 'SUCCESS' }">{{ trace.status }}</span></td>
              <td>{{ formatDate(trace.executedAt) }}</td>
              <td><button class="ghost-btn compact" type="button" @click="emit('loadDetail', trace.id, trace.traceId)">查看链路</button></td>
            </tr>
            <tr v-if="rows.length === 0">
              <td colspan="8" class="empty-cell">暂无链路数据，开始聊天后这里会展示会话与消息链路。</td>
            </tr>
          </tbody>
        </table>
      </div>
      <AdminTablePagination :page="adminTracePage" :page-size="adminTracePageSize" :total="adminTraceTotal" @change="emit('pageChange', $event)" />
    </section>
  </template>

  <template v-else>
    <div class="page-head trace-detail-head">
      <div>
        <p class="muted-line">RAG 链路列表 / 链路详情</p>
        <h1>rag-stream-chat <span class="status-pill success">SUCCESS</span></h1>
        <p># {{ selectedAdminTrace.id }} · {{ formatDate(selectedAdminTrace.latest_message_at) }} · {{ selectedAdminTrace.owner_username || selectedAdminTrace.owner_id || "unknown" }}</p>
      </div>
      <div class="page-actions">
        <button class="ghost-btn" type="button" @click="emit('back')">返回列表</button>
        <button class="ghost-btn" type="button" @click="emit('refreshDetail', selectedAdminTrace.id, selectedAdminTrace.trace_id)">刷新</button>
      </div>
    </div>

    <section class="trace-summary-strip">
      <article><span>节点</span><strong>{{ selectedTraceStats.nodeCount }}</strong></article>
      <article><span>成功</span><strong>{{ selectedTraceStats.successCount }}</strong></article>
      <article><span>失败</span><strong>{{ selectedTraceStats.failedCount }}</strong></article>
      <article><span>用户消息</span><strong>{{ selectedTraceStats.userMessages }}</strong></article>
      <article><span>助手回复</span><strong>{{ selectedTraceStats.assistantMessages }}</strong></article>
    </section>

    <section class="trace-detail-grid">
      <article class="table-card trace-timeline-card">
        <div class="table-toolbar">
          <div>
            <h2>执行时序</h2>
            <p>按真实 RAG 节点展示问题改写、意图识别、路由、检索、工具调用和生成耗时。</p>
          </div>
        </div>
        <AdminTraceTreePanel
          v-if="selectedAdminTraceNodes.length > 0"
          :nodes="selectedAdminTraceNodes"
          :format-duration="formatDuration"
          :format-date="formatDate"
        />
        <div v-else class="trace-timeline">
          <div class="trace-axis">
            <span>开始</span>
            <span>检索 / 工具</span>
            <span>生成</span>
            <span>完成</span>
          </div>
          <div v-for="node in selectedTraceRows" :key="node.id" class="trace-node-row">
            <div class="trace-node-name">
              <span class="trace-dot"></span>
              <strong>{{ node.name }}</strong>
              <small>{{ node.type }}</small>
            </div>
            <div class="trace-bar-track">
              <span class="trace-bar" :style="{ left: `${node.offset}%`, width: `${node.width}%` }"></span>
            </div>
            <div class="trace-node-duration">
              <strong>{{ node.duration }}</strong>
              <small>{{ formatDate(node.startedAt) }}</small>
            </div>
          </div>
        </div>
      </article>
    </section>

    <section class="table-card section-gap">
      <div class="table-toolbar">
        <div>
          <h2>消息链路</h2>
          <p>展示本次会话中的用户输入与助手输出摘要。</p>
        </div>
      </div>
      <div class="trace-message-list">
        <article v-for="message in selectedAdminTrace.messages" :key="message.id" class="trace-message-item" :class="message.role">
          <span class="status-pill">{{ message.role }}</span>
          <div>
            <strong>#{{ message.id }} · {{ formatDate(message.created_at) }}</strong>
            <p>{{ message.content_preview }}</p>
          </div>
        </article>
      </div>
    </section>
  </template>
</template>

<style scoped>
.muted-line {
  margin: 4px 0 0;
  color: #8794aa;
  font-size: 12px;
}

.trace-summary-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.trace-summary-strip article {
  border: 1px solid #dbe4f0;
  border-radius: 12px;
  padding: 14px;
  background: #fff;
}

.trace-summary-strip span {
  color: #64748b;
  font-size: 12px;
}

.trace-summary-strip strong {
  display: block;
  margin-top: 6px;
  color: #172033;
  font-size: 22px;
}

.trace-timeline {
  display: grid;
  gap: 14px;
  padding: 18px;
}

.trace-axis,
.trace-node-row {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr) 130px;
  gap: 16px;
  align-items: center;
}

.trace-axis {
  grid-template-columns: repeat(4, 1fr);
  padding-left: 176px;
  color: #8794aa;
  font-size: 12px;
}

.trace-node-name {
  display: grid;
  gap: 2px;
}

.trace-node-name small,
.trace-node-duration small {
  color: #8794aa;
}

.trace-bar-track {
  position: relative;
  height: 12px;
  border-radius: 999px;
  background: #eef2f7;
}

.trace-bar {
  position: absolute;
  top: 0;
  bottom: 0;
  border-radius: 999px;
  background: #6d3df5;
}

.trace-message-list {
  display: grid;
  gap: 10px;
  padding: 18px;
}

.trace-message-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  border: 1px solid #e9eef6;
  border-radius: 10px;
  padding: 12px;
}

.trace-message-item p {
  margin: 6px 0 0;
  color: #40506b;
}

.section-gap {
  margin-top: 16px;
}

@media (max-width: 1100px) {
  .trace-summary-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
