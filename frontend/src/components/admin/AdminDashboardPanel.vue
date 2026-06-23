<script setup lang="ts">
import { computed } from "vue";

import type {
  AdminDashboardMetricCard,
  AdminDashboardOpsInsight,
  AdminDashboardResponse,
  AdminDashboardSeries,
  AdminDashboardTrendPanel
} from "../../services/api";

const props = defineProps<{
  dashboard: AdminDashboardResponse | null;
  dashboardRange: string;
}>();

const emit = defineEmits<{
  changeRange: [value: string];
  refresh: [];
}>();

const rangeOptions = [
  { label: "24h", value: "24h" },
  { label: "7d", value: "7d" },
  { label: "30d", value: "30d" }
] as const;

const chartLabels = computed(() => props.dashboard?.traffic_overview.labels ?? []);
const axisLabels = computed(() => {
  const labels = chartLabels.value;
  const step = labels.length > 14 ? 5 : labels.length > 8 ? 2 : 1;
  return labels
    .map((label, index) => ({ label, index }))
    .filter(({ index }) => index === 0 || index === labels.length - 1 || index % step === 0)
    .map((item) => ({
      ...item,
      left: labels.length > 1 ? `${(item.index / (labels.length - 1)) * 100}%` : "50%",
      edge: item.index === 0 ? "start" : item.index === labels.length - 1 ? "end" : "middle"
    }));
});
const trafficSeries = computed(() => props.dashboard?.traffic_overview.series ?? []);
const trendPanels = computed(() => props.dashboard?.trend_panels ?? []);
const qualitySnapshot = computed(() => props.dashboard?.quality_snapshot ?? []);
const opsEfficiency = computed(() => props.dashboard?.ops_efficiency ?? []);
const coreCards = computed(() => props.dashboard?.core ?? []);
const insights = computed(() => props.dashboard?.ops_insights ?? []);

function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

function formatDuration(ms: number): string {
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  return `${ms}ms`;
}

function toChartPoints(values: number[], width = 720, height = 240): string {
  if (values.length === 0) {
    return "";
  }
  const maxValue = Math.max(...values, 1);
  const stepX = values.length > 1 ? width / (values.length - 1) : width / 2;
  return values
    .map((value, index) => {
      const x = values.length > 1 ? index * stepX : width / 2;
      const y = height - (value / maxValue) * (height - 24) - 12;
      return `${x},${y}`;
    })
    .join(" ");
}

function toAreaPath(values: number[], width = 720, height = 240): string {
  const line = toChartPoints(values, width, height);
  if (!line) {
    return "";
  }
  const points = line.split(" ");
  return `M 0 ${height} L ${points.join(" L ")} L ${width} ${height} Z`;
}

function seriesMax(series: AdminDashboardSeries[]): number {
  return Math.max(1, ...series.flatMap((item) => item.values));
}

const performanceGauge = computed(() => {
  const rate = props.dashboard?.ai_performance.success_rate ?? 0;
  const clamped = Math.max(0, Math.min(100, rate));
  return {
    degree: (clamped / 100) * 270 - 135,
    label: formatPercent(clamped)
  };
});

const trafficSummary = computed(() => {
  const traffic = props.dashboard?.traffic_overview;
  if (!traffic) {
    return [];
  }
  return [
    { label: "总消息", value: String(traffic.total_messages) },
    { label: "总会话", value: String(traffic.total_sessions) },
    { label: "活跃用户", value: String(traffic.total_active_users) }
  ];
});

function metricTone(card: AdminDashboardMetricCard): string {
  if (card.key.includes("error") || card.key.includes("slow") || card.key.includes("no_answer")) {
    return "warning";
  }
  if (card.key.includes("indexed")) {
    return "success";
  }
  return "neutral";
}

function insightTone(insight: AdminDashboardOpsInsight): string {
  return insight.level || "info";
}
</script>

<template>
  <section class="dashboard-panel">
    <div class="dashboard-head">
      <div>
        <h1>Dashboard</h1>
        <p>围绕真实会话、检索和入库数据，观察 RetriFlow 在 {{ dashboard?.range_label || "当前时间窗" }} 的运营状态。</p>
      </div>
      <div class="dashboard-actions">
        <div class="range-switch">
          <button
            v-for="option in rangeOptions"
            :key="option.value"
            type="button"
            :class="{ active: dashboardRange === option.value }"
            @click="emit('changeRange', option.value)"
          >
            {{ option.label }}
          </button>
        </div>
        <button class="refresh-btn" type="button" @click="emit('refresh')">刷新</button>
      </div>
    </div>

    <div class="core-grid">
      <article v-for="card in coreCards" :key="card.key" class="core-card">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.helper }}</small>
        <em v-if="card.delta">{{ card.delta }}</em>
      </article>
    </div>

    <div class="hero-grid">
      <article class="panel-card traffic-card">
        <div class="panel-head">
          <div>
            <h2>流量概览</h2>
            <p>{{ dashboard?.range_label || "当前时间窗" }} 下的消息、会话和活跃用户变化。</p>
          </div>
          <div class="traffic-mini-stats">
            <span v-for="item in trafficSummary" :key="item.label">
              <i>{{ item.label }}</i>
              <strong>{{ item.value }}</strong>
            </span>
          </div>
        </div>

        <div v-if="dashboard" class="main-chart">
          <svg viewBox="0 0 720 260" preserveAspectRatio="none" aria-label="traffic-overview-chart">
            <defs>
              <linearGradient id="traffic-area" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stop-color="rgba(49,94,251,0.24)" />
                <stop offset="100%" stop-color="rgba(49,94,251,0.02)" />
              </linearGradient>
            </defs>
            <g class="chart-grid">
              <line v-for="index in 5" :key="index" :x1="0" :x2="720" :y1="index * 43" :y2="index * 43" />
            </g>
            <path
              v-if="trafficSeries[0]"
              :d="toAreaPath(trafficSeries[0].values)"
              fill="url(#traffic-area)"
              stroke="none"
            />
            <polyline
              v-for="series in trafficSeries"
              :key="series.key"
              :points="toChartPoints(series.values)"
              fill="none"
              :stroke="series.color"
              stroke-width="4"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <g v-for="series in trafficSeries" :key="`${series.key}-dots`">
              <circle
                v-for="(value, index) in series.values"
                :key="`${series.key}-${index}`"
                :cx="series.values.length > 1 ? (720 / (series.values.length - 1)) * index : 360"
                :cy="240 - (value / Math.max(1, seriesMax(trafficSeries))) * 216 - 12"
                r="3.8"
                :fill="series.color"
              />
            </g>
          </svg>
          <div class="chart-labels">
            <span
              v-for="item in axisLabels"
              :key="`${item.index}-${item.label}`"
              :class="item.edge"
              :style="{ left: item.left }"
            >
              {{ item.label }}
            </span>
          </div>
          <div class="chart-legend">
            <span v-for="series in trafficSeries" :key="series.key">
              <i :style="{ backgroundColor: series.color }"></i>
              {{ series.label }}
            </span>
          </div>
        </div>
      </article>

      <article class="panel-card ai-card">
        <div class="panel-head">
          <div>
            <h2>AI 性能</h2>
            <p>回答完成率、时延与未命中率联合观测。</p>
          </div>
        </div>
        <div v-if="dashboard" class="ai-performance">
          <div class="gauge-card">
            <div class="gauge-shell">
              <div class="gauge-arc"></div>
              <div class="gauge-pointer" :style="{ transform: `rotate(${performanceGauge.degree}deg)` }"></div>
              <div class="gauge-center">
                <small>成功率</small>
                <strong>{{ performanceGauge.label }}</strong>
              </div>
            </div>
          </div>
          <div class="ai-metrics">
            <div class="ai-metric">
              <span>平均响应</span>
              <strong>{{ formatDuration(dashboard.ai_performance.avg_response_ms) }}</strong>
            </div>
            <div class="ai-metric">
              <span>P95 响应</span>
              <strong>{{ formatDuration(dashboard.ai_performance.p95_response_ms) }}</strong>
            </div>
            <div class="ai-metric">
              <span>完成率</span>
              <strong>{{ formatPercent(dashboard.ai_performance.completion_rate) }}</strong>
            </div>
            <div class="ai-metric">
              <span>未命中率</span>
              <strong>{{ formatPercent(dashboard.ai_performance.no_answer_rate) }}</strong>
            </div>
          </div>
        </div>
        <div class="quality-bars">
          <div
            v-for="card in qualitySnapshot.slice(0, 3)"
            :key="card.key"
            class="quality-bar"
            :class="metricTone(card)"
          >
            <div>
              <span>{{ card.label }}</span>
              <strong>{{ card.value }}</strong>
            </div>
            <small>{{ card.helper }}</small>
          </div>
        </div>
      </article>
    </div>

    <div class="dashboard-body">
      <div class="trend-section">
        <div class="section-head">
          <div>
            <h2>趋势分析</h2>
            <p>24h / 7d / 30d 会同时改变横轴粒度、曲线数值和质量走势。</p>
          </div>
        </div>
        <div class="trend-grid">
          <article v-for="panel in trendPanels" :key="panel.key" class="panel-card trend-card">
            <div class="panel-head compact">
              <div>
                <h3>{{ panel.label }}</h3>
                <p>{{ panel.summary }}</p>
              </div>
              <span class="panel-unit">{{ panel.unit }}</span>
            </div>
            <div class="mini-chart">
              <svg viewBox="0 0 320 180" preserveAspectRatio="none">
                <g class="chart-grid">
                  <line v-for="index in 4" :key="index" :x1="0" :x2="320" :y1="index * 36" :y2="index * 36" />
                </g>
                <polyline
                  v-for="series in panel.series"
                  :key="series.key"
                  :points="toChartPoints(series.values, 320, 180)"
                  fill="none"
                  :stroke="series.color"
                  stroke-width="3.25"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
              <div class="mini-labels">
                <span
                  v-for="item in axisLabels"
                  :key="`${panel.key}-${item.index}-${item.label}`"
                  :class="item.edge"
                  :style="{ left: item.left }"
                >
                  {{ item.label }}
                </span>
              </div>
            </div>
            <div class="chart-legend mini">
              <span v-for="series in panel.series" :key="`${panel.key}-${series.key}`">
                <i :style="{ backgroundColor: series.color }"></i>
                {{ series.label }}
              </span>
            </div>
          </article>
        </div>
      </div>

      <aside class="side-section">
        <article class="panel-card">
          <div class="section-head">
            <div>
              <h2>质量快照</h2>
              <p>结合索引、兜底、慢响应与任务失败观察质量面。</p>
            </div>
          </div>
          <div class="metric-stack">
            <div v-for="card in qualitySnapshot" :key="card.key" class="metric-row" :class="metricTone(card)">
              <div>
                <span>{{ card.label }}</span>
                <strong>{{ card.value }}</strong>
              </div>
              <small>{{ card.helper }}</small>
              <em v-if="card.delta">{{ card.delta }}</em>
            </div>
          </div>
        </article>

        <article class="panel-card">
          <div class="section-head">
            <div>
              <h2>运营效率</h2>
              <p>更偏业务观察，不再展示无意义 Top 列表。</p>
            </div>
          </div>
          <div class="metric-stack">
            <div v-for="card in opsEfficiency" :key="card.key" class="metric-row">
              <div>
                <span>{{ card.label }}</span>
                <strong>{{ card.value }}</strong>
              </div>
              <small>{{ card.helper }}</small>
            </div>
          </div>
        </article>
      </aside>
    </div>

    <article class="panel-card insight-card">
      <div class="section-head">
        <div>
          <h2>运营洞察</h2>
          <p>由当前窗口真实数据自动归纳出的重点提醒。</p>
        </div>
      </div>
      <div class="insight-grid">
        <article v-for="insight in insights" :key="`${insight.category}-${insight.title}`" class="insight-item" :class="insightTone(insight)">
          <div class="insight-meta">
            <span>{{ insight.category }}</span>
            <small>{{ insight.time_label }}</small>
          </div>
          <strong>{{ insight.title }}</strong>
          <p>{{ insight.message }}</p>
        </article>
      </div>
    </article>
  </section>
</template>

<style scoped>
.dashboard-panel {
  display: grid;
  gap: 20px;
}

.dashboard-head,
.panel-head,
.section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.dashboard-head {
  align-items: center;
}

.dashboard-head h1,
.section-head h2,
.panel-head h2,
.panel-head h3 {
  margin: 0;
  color: #162033;
}

.dashboard-head p,
.panel-head p,
.section-head p {
  display: none;
  margin: 0;
  color: #607089;
  line-height: 1.5;
}

.dashboard-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.range-switch {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border: 1px solid #dce6f2;
  border-radius: 14px;
  background: #eef4fb;
}

.range-switch button,
.refresh-btn {
  min-height: 40px;
  border: 0;
  border-radius: 8px;
  padding: 0 16px;
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}

.range-switch button {
  background: transparent;
  color: #596b85;
}

.range-switch button.active {
  background: #ffffff;
  color: #315efb;
  box-shadow: 0 10px 22px rgba(22, 32, 51, 0.08);
}

.refresh-btn {
  background: #ffffff;
  border: 1px solid #dce6f2;
  color: #31435f;
}

.core-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.core-card,
.panel-card {
  border: 1px solid rgba(222, 230, 240, 0.92);
  border-radius: 20px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}

.core-card {
  display: grid;
  min-height: 118px;
  gap: 7px;
  padding: 18px 20px;
}

.core-card span,
.metric-row span,
.quality-bar span,
.ai-metric span,
.traffic-mini-stats i {
  color: #6a7a92;
  font-size: 14px;
  font-style: normal;
}

.core-card strong,
.metric-row strong,
.quality-bar strong,
.ai-metric strong,
.traffic-mini-stats strong {
  color: #162033;
  font-size: 28px;
  line-height: 1;
}

.core-card small,
.core-card em,
.metric-row small,
.metric-row em,
.quality-bar small {
  color: #7c8ba3;
  font-style: normal;
}

.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(340px, 0.9fr);
  gap: 20px;
}

.panel-card {
  padding: 18px 22px;
}

.traffic-mini-stats {
  display: flex;
  gap: 18px;
  align-items: center;
}

.traffic-mini-stats span {
  display: grid;
  gap: 6px;
}

.main-chart,
.mini-chart {
  margin-top: 16px;
}

.main-chart svg,
.mini-chart svg {
  width: 100%;
  height: 210px;
  display: block;
}

.mini-chart svg {
  height: 150px;
}

.chart-grid line {
  stroke: rgba(155, 169, 189, 0.2);
  stroke-width: 1;
}

.chart-labels,
.mini-labels {
  position: relative;
  height: 16px;
  margin-top: 10px;
  color: #8a98b1;
  font-size: 10px;
  line-height: 16px;
}

.chart-labels span,
.mini-labels span {
  position: absolute;
  top: 0;
  max-width: 54px;
  transform: translateX(-50%);
  text-align: center;
  overflow: visible;
  white-space: nowrap;
}

.chart-labels span.start,
.mini-labels span.start {
  transform: translateX(0);
  text-align: left;
}

.chart-labels span.end,
.mini-labels span.end {
  transform: translateX(-100%);
  text-align: right;
}

.chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 12px;
  color: #5d6d86;
  font-size: 13px;
}

.chart-legend span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.chart-legend i {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  display: inline-block;
}

.chart-legend.mini {
  margin-top: 14px;
  font-size: 12px;
}

.ai-performance {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 14px;
  margin-top: 16px;
}

.gauge-card {
  display: grid;
  place-items: center;
}

.gauge-shell {
  position: relative;
  width: 136px;
  height: 136px;
  display: grid;
  place-items: center;
}

.gauge-arc {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background:
    conic-gradient(from 225deg, #315efb 0deg, #00a87e 190deg, rgba(214, 223, 238, 0.4) 190deg, rgba(214, 223, 238, 0.4) 270deg);
  -webkit-mask: radial-gradient(circle at center, transparent 58%, #000 59%);
  mask: radial-gradient(circle at center, transparent 58%, #000 59%);
}

.gauge-pointer {
  position: absolute;
  width: 76px;
  height: 3px;
  background: linear-gradient(90deg, #172033, #315efb);
  border-radius: 999px;
  transform-origin: 50% 50%;
}

.gauge-center {
  position: relative;
  width: 82px;
  height: 82px;
  display: grid;
  place-items: center;
  gap: 6px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: inset 0 0 0 1px rgba(216, 225, 237, 0.9);
}

.gauge-center small {
  color: #8090a9;
}

.gauge-center strong {
  font-size: 24px;
}

.ai-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.ai-metric,
.quality-bar,
.metric-row,
.insight-item {
  border-radius: 18px;
  border: 1px solid #e4ebf4;
  background: rgba(255, 255, 255, 0.92);
}

.ai-metric {
  display: grid;
  gap: 6px;
  padding: 10px 12px;
}

.quality-bars {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.quality-bar {
  display: grid;
  align-content: start;
  gap: 6px;
  padding: 12px 14px;
}

.quality-bar.success {
  background: linear-gradient(180deg, rgba(236, 253, 245, 0.95), rgba(255, 255, 255, 0.95));
}

.quality-bar.warning {
  background: linear-gradient(180deg, rgba(255, 247, 237, 0.95), rgba(255, 255, 255, 0.95));
}

.dashboard-body {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(320px, 0.72fr);
  align-items: stretch;
  gap: 20px;
}

.trend-section,
.side-section {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  align-content: stretch;
}

.trend-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 14px;
}

.trend-card {
  padding: 16px;
}

.panel-head.compact,
.section-head {
  align-items: flex-start;
}

.panel-unit {
  padding: 8px 10px;
  border-radius: 999px;
  background: #eef4fb;
  color: #4b617d;
  font-size: 12px;
  font-weight: 800;
}

.side-section {
  gap: 16px;
}

.metric-stack {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.metric-row {
  display: grid;
  gap: 6px;
  padding: 12px;
}

.metric-row.warning {
  background: linear-gradient(180deg, rgba(255, 247, 237, 0.96), rgba(255, 255, 255, 0.96));
}

.metric-row.success {
  background: linear-gradient(180deg, rgba(240, 253, 244, 0.96), rgba(255, 255, 255, 0.96));
}

.insight-card {
  padding: 18px 22px;
}

.insight-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.insight-item {
  display: grid;
  gap: 10px;
  padding: 14px;
}

.insight-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.insight-meta span {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 5px 10px;
  background: #edf3ff;
  color: #315efb;
  font-size: 12px;
  font-weight: 800;
}

.insight-meta small {
  color: #8796ac;
}

.insight-item strong {
  color: #162033;
  font-size: 18px;
}

.insight-item p {
  margin: 0;
  color: #62728b;
  line-height: 1.7;
}

.insight-item.success {
  background: linear-gradient(180deg, rgba(240, 253, 244, 0.98), rgba(255, 255, 255, 0.96));
}

.insight-item.warning {
  background: linear-gradient(180deg, rgba(255, 247, 237, 0.98), rgba(255, 255, 255, 0.96));
}

.insight-item.danger {
  background: linear-gradient(180deg, rgba(254, 242, 242, 0.98), rgba(255, 255, 255, 0.96));
}

@media (max-width: 1280px) {
  .core-grid,
  .hero-grid,
  .dashboard-body,
  .quality-bars,
  .trend-grid,
  .insight-grid {
    grid-template-columns: 1fr;
  }

  .ai-performance {
    grid-template-columns: 1fr;
  }

  .traffic-mini-stats {
    flex-wrap: wrap;
  }
}

@media (max-width: 720px) {
  .dashboard-head,
  .dashboard-actions,
  .panel-head,
  .section-head {
    flex-direction: column;
    align-items: stretch;
  }

  .core-grid {
    grid-template-columns: 1fr;
  }

  .ai-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
