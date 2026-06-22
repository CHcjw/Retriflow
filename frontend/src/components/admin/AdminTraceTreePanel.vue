<script setup lang="ts">
import { computed } from "vue";
import type { AdminTraceNodeItem } from "../../services/api";

type TraceTimelineNode = AdminTraceNodeItem & {
  children: TraceTimelineNode[];
  depth: number;
  offsetMs: number;
  leftPercent: number;
  widthPercent: number;
};

const props = defineProps<{
  nodes: AdminTraceNodeItem[];
  formatDuration: (durationMs: number) => string;
  formatDate: (value: string) => string;
}>();

const timeline = computed(() => {
  const byId = new Map<string, TraceTimelineNode>();
  props.nodes.forEach((node) => {
    byId.set(node.id, {
      ...node,
      children: [],
      depth: 0,
      offsetMs: 0,
      leftPercent: 0,
      widthPercent: 4
    });
  });

  const roots: TraceTimelineNode[] = [];
  byId.forEach((node) => {
    const parent = node.parent_id ? byId.get(node.parent_id) : undefined;
    if (parent) {
      parent.children.push(node);
      return;
    }
    roots.push(node);
  });

  const sortAndFlatten = (items: TraceTimelineNode[], depth: number, rows: TraceTimelineNode[]) => {
    items.sort((left, right) => Date.parse(left.started_at) - Date.parse(right.started_at));
    items.forEach((item) => {
      item.depth = depth;
      rows.push(item);
      sortAndFlatten(item.children, depth + 1, rows);
    });
  };

  const rows: TraceTimelineNode[] = [];
  sortAndFlatten(roots, 0, rows);

  const starts = rows.map((node) => Date.parse(node.started_at)).filter((value) => Number.isFinite(value));
  const firstStart = starts.length ? Math.min(...starts) : 0;
  const maxEnd = rows.reduce((current, node) => {
    const started = Date.parse(node.started_at);
    const finished = Date.parse(node.finished_at);
    if (Number.isFinite(finished)) return Math.max(current, finished);
    if (Number.isFinite(started)) return Math.max(current, started + Math.max(0, node.duration_ms || 0));
    return current;
  }, firstStart);
  const totalWindowMs = Math.max(1, maxEnd - firstStart, ...rows.map((node) => node.duration_ms || 0));

  rows.forEach((node) => {
    const started = Date.parse(node.started_at);
    const offsetMs = Number.isFinite(started) ? Math.max(0, started - firstStart) : 0;
    const durationMs = Math.max(0, node.duration_ms || 0);
    node.offsetMs = offsetMs;
    node.leftPercent = Math.min(92, Math.max(0, (offsetMs / totalWindowMs) * 100));
    node.widthPercent = durationMs > 0 ? Math.max(3, Math.min(96 - node.leftPercent, (durationMs / totalWindowMs) * 100)) : 3;
  });

  const slowestNodeId = rows.reduce<string | null>((current, node) => {
    if (!current) return node.id;
    const currentNode = rows.find((item) => item.id === current);
    return (node.duration_ms || 0) > (currentNode?.duration_ms || 0) ? node.id : current;
  }, null);

  return {
    rows,
    slowestNodeId,
    totalWindowMs
  };
});

const stats = computed(() => {
  const durations = props.nodes.map((node) => node.duration_ms || 0).filter((value) => value > 0);
  return {
    total: props.nodes.length,
    success: props.nodes.filter((node) => node.status === "success").length,
    failed: props.nodes.filter((node) => node.status === "error").length,
    average: durations.length ? Math.round(durations.reduce((sum, value) => sum + value, 0) / durations.length) : 0
  };
});

const scaleMarks = computed(() => {
  const total = timeline.value.totalWindowMs;
  return [0, 0.25, 0.5, 0.75, 1].map((ratio) => ({
    label: props.formatDuration(Math.round(total * ratio)),
    left: `${ratio * 100}%`
  }));
});

function statusClass(status: string) {
  const normalized = status.trim().toLowerCase();
  return {
    success: normalized === "success",
    warning: normalized === "running" || normalized === "cancelled",
    danger: normalized === "error"
  };
}

function summary(node: AdminTraceNodeItem) {
  return node.error_message || node.output_summary || node.input_summary || "";
}

function displayName(name: string) {
  const names: Record<string, string> = {
    "chat.stream": "流式对话",
    "generation.answer": "生成回答",
    "user-first-packet": "用户感知首包",
    "llm-first-packet": "LLM 首包",
    "llm-stream-routing": "LLM 流式路由",
    "retrieval-engine": "知识库检索",
    "multi-channel-retrieval": "多路召回",
    "context-build": "上下文组装",
    "prompt-render": "Prompt 渲染",
    "query-rewrite-and-split": "问题改写与拆分",
    "intent-resolve": "意图识别",
    "guidance-detect": "歧义引导"
  };
  return names[name] || name;
}
</script>

<template>
  <section class="trace-execution-card">
    <header class="trace-execution-head">
      <div>
        <h2>执行时序</h2>
      </div>
      <span>{{ stats.total }} 节点 · {{ props.formatDuration(timeline.totalWindowMs) }}</span>
    </header>

    <div v-if="timeline.rows.length > 0" class="trace-table">
      <div class="trace-table-head">
        <span>节点</span>
        <span>类型</span>
        <span>时间线</span>
        <span>耗时</span>
      </div>

      <div class="trace-scale">
        <span></span>
        <span></span>
        <div class="trace-scale-track">
          <span v-for="mark in scaleMarks" :key="mark.label" :style="{ left: mark.left }">{{ mark.label }}</span>
        </div>
        <span></span>
      </div>

      <div
        v-for="node in timeline.rows"
        :key="node.id"
        class="trace-row"
        :class="{ root: node.depth === 0, slowest: node.id === timeline.slowestNodeId && node.depth > 0 }"
      >
        <div class="trace-node-cell" :style="{ paddingLeft: `${node.depth * 22 + 2}px` }">
          <span v-if="node.depth > 0" class="trace-branch" aria-hidden="true"></span>
          <span class="trace-dot" :class="statusClass(node.status)"></span>
          <div>
            <strong>{{ displayName(node.name) }}</strong>
            <small v-if="summary(node)">{{ summary(node) }}</small>
          </div>
        </div>
        <div class="trace-type-cell">{{ node.node_type }}</div>
        <div class="trace-line-cell">
          <span class="trace-line-bar" :class="statusClass(node.status)" :style="{ left: `${node.leftPercent}%`, width: `${node.widthPercent}%` }"></span>
        </div>
        <div class="trace-duration-cell">
          <strong>{{ props.formatDuration(node.duration_ms || 0) }}</strong>
          <small>@{{ props.formatDuration(node.offsetMs) }}</small>
          <small>{{ props.formatDate(node.started_at) }}</small>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">暂无节点记录</div>
  </section>
</template>

<style scoped>
.trace-execution-card {
  overflow: hidden;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 8px;
  background: #ffffff;
}

.trace-execution-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 24px 16px;
}

.trace-execution-head h2 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}

.trace-execution-head p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.trace-execution-head span,
.trace-metric-line span {
  color: #475569;
  font-size: 13px;
  white-space: nowrap;
}

.trace-metric-line {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 0 24px 16px;
}

.trace-table {
  border-top: 1px solid rgba(15, 23, 42, 0.08);
}

.trace-table-head,
.trace-scale,
.trace-row {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 120px minmax(260px, 2fr) 108px;
  align-items: center;
  gap: 16px;
  padding: 0 16px;
}

.trace-table-head {
  min-height: 38px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.trace-scale {
  min-height: 32px;
}

.trace-scale-track {
  position: relative;
  height: 100%;
  border-bottom: 1px solid #e2e8f0;
}

.trace-scale-track span {
  position: absolute;
  bottom: 6px;
  transform: translateX(-50%);
  color: #94a3b8;
  font-size: 11px;
}

.trace-row {
  min-height: 58px;
  border-top: 1px solid rgba(15, 23, 42, 0.05);
  transition: background 0.16s ease;
}

.trace-row.root {
  background: #eef2ff;
}

.trace-row.slowest {
  background: #fffbeb;
}

.trace-row:hover {
  background: #f8fafc;
}

.trace-node-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.trace-branch {
  width: 16px;
  height: 28px;
  flex: 0 0 auto;
  margin-left: -6px;
  border-bottom: 1px solid #cbd5e1;
  border-left: 1px solid #cbd5e1;
}

.trace-node-cell strong,
.trace-node-cell small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-node-cell strong {
  color: #0f172a;
  font-size: 14px;
}

.trace-node-cell small {
  margin-top: 3px;
  color: #64748b;
  font-size: 11px;
}

.trace-dot {
  width: 9px;
  height: 9px;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #94a3b8;
}

.trace-dot.success,
.trace-line-bar.success {
  background: #34d399;
}

.trace-dot.warning,
.trace-line-bar.warning {
  background: #f59e0b;
}

.trace-dot.danger,
.trace-line-bar.danger {
  background: #ef4444;
}

.trace-type-cell {
  display: inline-flex;
  justify-self: start;
  max-width: 100%;
  overflow: hidden;
  border-radius: 6px;
  padding: 5px 9px;
  background: #f1f5f9;
  color: #57708f;
  font-size: 12px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-line-cell {
  position: relative;
  height: 26px;
  overflow: hidden;
  border-radius: 6px;
  background: #f8fafc;
}

.trace-line-cell::before,
.trace-line-cell::after {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: #dbe4f0;
  content: "";
}

.trace-line-cell::before {
  left: 25%;
}

.trace-line-cell::after {
  left: 75%;
}

.trace-line-bar {
  position: absolute;
  top: 5px;
  bottom: 5px;
  min-width: 4px;
  border-radius: 4px;
  background: #34d399;
}

.trace-duration-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  color: #64748b;
}

.trace-duration-cell strong {
  color: #0f172a;
  font-size: 14px;
}

.trace-duration-cell small {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 10px;
}

.empty-state {
  padding: 46px 16px;
  color: #94a3b8;
  text-align: center;
}

@media (max-width: 980px) {
  .trace-execution-head {
    flex-direction: column;
  }

  .trace-table {
    overflow-x: auto;
  }

  .trace-table-head,
  .trace-scale,
  .trace-row {
    min-width: 760px;
  }
}
</style>
