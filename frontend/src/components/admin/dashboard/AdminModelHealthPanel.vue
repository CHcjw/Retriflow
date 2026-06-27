<script setup lang="ts">
import { computed, onMounted, shallowRef } from "vue";

import {
  fetchAdminModelHealth,
  probeAdminModelHealth,
  type AdminModelHealthItem
} from "../../../services/adminApi";

const loading = shallowRef(false);
const probing = shallowRef(false);
const error = shallowRef("");
const items = shallowRef<AdminModelHealthItem[]>([]);
const probeCapability = shallowRef("chat");
const probeProvider = shallowRef("");
const probeModelName = shallowRef("");

const sortedItems = computed(() =>
  [...items.value].sort((a, b) =>
    `${a.capability}:${a.provider_name}:${a.model}`.localeCompare(`${b.capability}:${b.provider_name}:${b.model}`)
  )
);

const summary = computed(() => {
  const total = items.value.length;
  const healthy = items.value.filter((item) => item.state === "healthy").length;
  const open = items.value.filter((item) => item.state === "open").length;
  const halfOpen = items.value.filter((item) => item.state === "half_open").length;
  return { total, healthy, open, halfOpen };
});

async function loadModelHealth() {
  loading.value = true;
  error.value = "";
  try {
    const response = await fetchAdminModelHealth();
    items.value = response.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "模型健康数据加载失败";
  } finally {
    loading.value = false;
  }
}

async function runProbe() {
  probing.value = true;
  error.value = "";
  try {
    const snapshot = await probeAdminModelHealth({
      capability: probeCapability.value.trim() || "chat",
      provider_name: probeProvider.value.trim() || undefined,
      model: probeModelName.value.trim() || undefined
    });
    const key = snapshotKey(snapshot);
    const nextItems = items.value.filter((item) => snapshotKey(item) !== key);
    items.value = [...nextItems, snapshot];
  } catch (err) {
    error.value = err instanceof Error ? err.message : "模型探测失败";
  } finally {
    probing.value = false;
  }
}

function snapshotKey(item: AdminModelHealthItem) {
  return `${item.capability}:${item.provider_name}:${item.model}`;
}

function stateLabel(state: string) {
  if (state === "open") {
    return "熔断";
  }
  if (state === "half_open") {
    return "半开";
  }
  return "健康";
}

function stateClass(state: string) {
  return {
    "model-health-state": true,
    "model-health-state-open": state === "open",
    "model-health-state-half": state === "half_open",
    "model-health-state-healthy": state === "healthy"
  };
}

function formatTimestamp(value: number | null) {
  if (!value) {
    return "-";
  }
  return new Date(value * 1000).toLocaleString();
}

function formatDuration(value: number | null) {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${value} ms`;
}

onMounted(() => {
  void loadModelHealth();
});
</script>

<template>
  <section class="model-health-panel">
    <header class="model-health-head">
      <div>
        <h2>模型健康</h2>
        <p>Provider / Model 熔断状态与手动探测</p>
      </div>
      <button class="ghost-btn" type="button" :disabled="loading" @click="void loadModelHealth()">
        刷新
      </button>
    </header>

    <div class="model-health-summary">
      <div class="model-health-summary-item">
        <span>总数</span>
        <strong>{{ summary.total }}</strong>
      </div>
      <div class="model-health-summary-item">
        <span>健康</span>
        <strong>{{ summary.healthy }}</strong>
      </div>
      <div class="model-health-summary-item">
        <span>熔断</span>
        <strong>{{ summary.open }}</strong>
      </div>
      <div class="model-health-summary-item">
        <span>半开</span>
        <strong>{{ summary.halfOpen }}</strong>
      </div>
    </div>

    <form class="model-health-probe" @submit.prevent="void runProbe()">
      <label>
        <span>能力</span>
        <select v-model="probeCapability" class="ui-input pretty-select">
          <option value="chat">chat</option>
          <option value="route">route</option>
          <option value="rewrite">rewrite</option>
          <option value="memory_summary">memory_summary</option>
          <option value="embedding">embedding</option>
          <option value="rerank">rerank</option>
        </select>
      </label>
      <label>
        <span>Provider</span>
        <input v-model="probeProvider" class="ui-input" type="text" placeholder="留空使用当前路由，如 lmstudio" />
      </label>
      <label>
        <span>Model</span>
        <input v-model="probeModelName" class="ui-input" type="text" placeholder="留空使用默认模型" />
      </label>
      <button class="primary-btn" type="submit" :disabled="probing">
        {{ probing ? "探测中" : "探测" }}
      </button>
    </form>

    <p v-if="error" class="model-health-error">{{ error }}</p>

    <div class="table-shell model-health-table">
      <table>
        <thead>
          <tr>
            <th>能力</th>
            <th>Provider</th>
            <th>Model</th>
            <th>状态</th>
            <th>成功 / 失败</th>
            <th>最近成功</th>
            <th>最近失败</th>
            <th>首包</th>
            <th>错误</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="9">加载中</td>
          </tr>
          <tr v-else-if="sortedItems.length === 0">
            <td colspan="9">暂无模型健康快照</td>
          </tr>
          <template v-else>
            <tr v-for="item in sortedItems" :key="snapshotKey(item)">
              <td>{{ item.capability }}</td>
              <td>{{ item.provider_name }}</td>
              <td>{{ item.model }}</td>
              <td><span :class="stateClass(item.state)">{{ stateLabel(item.state) }}</span></td>
              <td>{{ item.success_count }} / {{ item.failure_count }}</td>
              <td>{{ formatTimestamp(item.last_success_at) }}</td>
              <td>{{ formatTimestamp(item.last_failure_at) }}</td>
              <td>{{ formatDuration(item.last_first_packet_ms) }}</td>
              <td class="model-health-error-cell">{{ item.last_error || "-" }}</td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <footer class="table-footer">共 {{ sortedItems.length }} 条</footer>
  </section>
</template>

<style scoped>
.model-health-panel {
  display: grid;
  gap: 16px;
}

.model-health-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.model-health-head h2 {
  margin: 0;
  font-size: 18px;
  color: #172033;
}

.model-health-head p {
  margin: 4px 0 0;
  color: #697386;
  font-size: 13px;
}

.model-health-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.model-health-summary-item {
  border: 1px solid #e4e8f0;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}

.model-health-summary-item span {
  display: block;
  color: #697386;
  font-size: 12px;
}

.model-health-summary-item strong {
  display: block;
  margin-top: 4px;
  color: #172033;
  font-size: 22px;
}

.model-health-probe {
  display: grid;
  grid-template-columns: 160px minmax(180px, 1fr) minmax(180px, 1fr) auto;
  align-items: end;
  gap: 12px;
}

.model-health-probe label {
  display: grid;
  gap: 6px;
  color: #4d5870;
  font-size: 12px;
}

.ui-input {
  width: 100%;
  min-height: 42px;
  border: 1px solid #d8deea;
  border-radius: 8px;
  padding: 9px 12px;
  background: #fff;
  color: #172033;
  font: inherit;
  outline: none;
}

.ui-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgb(59 130 246 / 14%);
}

.pretty-select {
  appearance: none;
  background-image:
    linear-gradient(45deg, transparent 50%, #697386 50%),
    linear-gradient(135deg, #697386 50%, transparent 50%);
  background-position:
    calc(100% - 17px) 18px,
    calc(100% - 12px) 18px;
  background-size:
    5px 5px,
    5px 5px;
  background-repeat: no-repeat;
  padding-right: 34px;
}

.ghost-btn,
.primary-btn {
  min-height: 42px;
  border-radius: 8px;
  padding: 0 16px;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.ghost-btn {
  border: 1px solid #d8deea;
  background: #fff;
  color: #344054;
}

.primary-btn {
  border: 1px solid #2563eb;
  background: #2563eb;
  color: #fff;
}

.ghost-btn:disabled,
.primary-btn:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.model-health-error {
  margin: 0;
  color: #b42318;
  font-size: 13px;
}

.model-health-table {
  overflow-x: auto;
  border: 1px solid #e4e8f0;
  border-radius: 8px;
  background: #fff;
}

.model-health-table table {
  width: 100%;
  min-width: 1040px;
  border-collapse: collapse;
}

.model-health-table th,
.model-health-table td {
  border-bottom: 1px solid #eef1f6;
  padding: 12px 14px;
  text-align: left;
  vertical-align: middle;
  color: #344054;
  font-size: 13px;
}

.model-health-table th {
  background: #f8fafc;
  color: #697386;
  font-size: 12px;
  font-weight: 700;
}

.model-health-table tbody tr:last-child td {
  border-bottom: 0;
}

.table-footer {
  color: #697386;
  font-size: 13px;
}

.model-health-state {
  display: inline-flex;
  align-items: center;
  min-width: 48px;
  justify-content: center;
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 12px;
  font-weight: 600;
}

.model-health-state-healthy {
  background: #e9f8ef;
  color: #16794c;
}

.model-health-state-open {
  background: #fff1f0;
  color: #b42318;
}

.model-health-state-half {
  background: #fff7e6;
  color: #9a5b00;
}

.model-health-error-cell {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 980px) {
  .model-health-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .model-health-probe {
    grid-template-columns: 1fr;
  }
}
</style>
