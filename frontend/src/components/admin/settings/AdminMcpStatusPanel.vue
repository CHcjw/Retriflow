<script setup lang="ts">
import { computed, onMounted, shallowRef } from "vue";

import { fetchAdminMcpStatus, type AdminMcpRemoteServerItem, type AdminMcpToolItem } from "../../../services/adminApi";

const loading = shallowRef(false);
const error = shallowRef("");
const tools = shallowRef<AdminMcpToolItem[]>([]);
const remoteServers = shallowRef<AdminMcpRemoteServerItem[]>([]);
const remoteEnabled = shallowRef(false);

const summary = computed(() => ({
  tools: tools.value.length,
  remoteServers: remoteServers.value.length,
  healthyServers: remoteServers.value.filter((server) => server.healthy).length
}));

function joinKeywords(keywords: string[]) {
  return keywords.length > 0 ? keywords.join(" / ") : "-";
}

async function loadStatus() {
  loading.value = true;
  error.value = "";
  try {
    const response = await fetchAdminMcpStatus();
    tools.value = response.tools;
    remoteServers.value = response.remote_servers;
    remoteEnabled.value = response.remote_enabled;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "MCP 状态加载失败";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadStatus();
});
</script>

<template>
  <section class="mcp-panel">
    <header class="mcp-head">
      <div>
        <h2>MCP 治理</h2>
        <p>展示当前工具注册、远程 Server 状态和健康概况。</p>
      </div>
      <button class="ghost-btn" type="button" :disabled="loading" @click="void loadStatus()">
        {{ loading ? "刷新中" : "刷新" }}
      </button>
    </header>

    <div class="mcp-summary">
      <div class="mcp-summary-item">
        <span>总工具</span>
        <strong>{{ summary.tools }}</strong>
      </div>
      <div class="mcp-summary-item">
        <span>远程 Server</span>
        <strong>{{ summary.remoteServers }}</strong>
      </div>
      <div class="mcp-summary-item">
        <span>健康 Server</span>
        <strong>{{ summary.healthyServers }}</strong>
      </div>
      <div class="mcp-summary-item">
        <span>远程启用</span>
        <strong>{{ remoteEnabled ? "是" : "否" }}</strong>
      </div>
    </div>

    <p v-if="error" class="mcp-error">{{ error }}</p>

    <section class="table-card mcp-table-card">
      <div class="table-toolbar compact-toolbar">
        <div>
          <h2>工具注册</h2>
          <p>内置工具与已加载远程工具的注册信息。</p>
        </div>
      </div>
      <div class="table-scroll">
        <table class="data-table mcp-tool-table">
          <colgroup>
            <col class="tool-col" />
            <col class="server-col" />
            <col class="transport-col" />
            <col class="schema-col" />
            <col class="count-col" />
            <col class="keyword-col" />
          </colgroup>
          <thead>
            <tr>
              <th>工具</th>
              <th>服务端</th>
              <th>传输</th>
              <th>Schema</th>
              <th>参数</th>
              <th>关键词</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="tool in tools" :key="tool.tool_id">
              <td class="mcp-mono" :title="tool.tool_id">{{ tool.tool_id }}</td>
              <td><span class="badge" :title="tool.server_name">{{ tool.server_name }}</span></td>
              <td><span class="status-pill">{{ tool.transport }}</span></td>
              <td class="mcp-mono" :title="tool.schema_version">{{ tool.schema_version }}</td>
              <td>{{ tool.parameter_count }}</td>
              <td class="mcp-keywords" :title="joinKeywords(tool.keywords)">{{ joinKeywords(tool.keywords) }}</td>
            </tr>
            <tr v-if="!loading && tools.length === 0">
              <td colspan="6" class="empty-cell">暂无 MCP 工具注册信息。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="table-card mcp-table-card">
      <div class="table-toolbar compact-toolbar">
        <div>
          <h2>远程 Server</h2>
          <p>按配置加载远程 Server，失败项只标记为不可用。</p>
        </div>
      </div>
      <div class="table-scroll">
        <table class="data-table mcp-server-table">
          <colgroup>
            <col class="remote-name-col" />
            <col class="remote-url-col" />
            <col class="remote-health-col" />
            <col class="remote-count-col" />
            <col class="remote-error-col" />
          </colgroup>
          <thead>
            <tr>
              <th>远程 Server</th>
              <th>地址</th>
              <th>健康</th>
              <th>工具数</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="server in remoteServers" :key="server.name">
              <td class="mcp-mono" :title="server.name">{{ server.name }}</td>
              <td class="mcp-url" :title="server.url">{{ server.url || "-" }}</td>
              <td>
                <span class="status-pill" :class="{ success: server.healthy, danger: !server.healthy }">
                  {{ server.healthy ? "healthy" : "unhealthy" }}
                </span>
              </td>
              <td>{{ server.tool_count }}</td>
              <td class="mcp-error-cell" :title="server.error || '-'">{{ server.error || "-" }}</td>
            </tr>
            <tr v-if="!loading && remoteServers.length === 0">
              <td colspan="5" class="empty-cell">暂无远程 Server 配置。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<style scoped>
.mcp-panel {
  margin-top: 16px;
  border: 1px solid #dbe4f0;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(34, 43, 63, 0.05);
  padding: 20px;
}

.mcp-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.mcp-head h2 {
  margin: 0 0 6px;
  color: #172033;
  font-size: 18px;
}

.mcp-head p,
.compact-toolbar p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.mcp-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.mcp-summary-item {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
}

.mcp-summary-item span {
  display: block;
  color: #64748b;
  font-size: 12px;
}

.mcp-summary-item strong {
  display: block;
  margin-top: 4px;
  color: #172033;
  font-size: 18px;
}

.mcp-error {
  margin: 0 0 12px;
  border: 1px solid #fecaca;
  border-radius: 8px;
  background: #fff1f2;
  color: #b91c1c;
  font-size: 13px;
  padding: 9px 12px;
}

.mcp-table-card {
  box-shadow: none;
}

.mcp-table-card + .mcp-table-card {
  margin-top: 14px;
}

.compact-toolbar {
  padding: 14px 16px 10px;
}

.compact-toolbar h2 {
  margin: 0 0 4px;
  color: #172033;
  font-size: 15px;
}

.mcp-tool-table,
.mcp-server-table {
  table-layout: fixed;
}

.tool-col {
  width: 20%;
}

.server-col {
  width: 14%;
}

.transport-col {
  width: 11%;
}

.schema-col {
  width: 14%;
}

.count-col {
  width: 8%;
}

.keyword-col {
  width: 33%;
}

.remote-name-col {
  width: 18%;
}

.remote-url-col {
  width: 36%;
}

.remote-health-col {
  width: 14%;
}

.remote-count-col {
  width: 10%;
}

.remote-error-col {
  width: 22%;
}

.mcp-mono,
.mcp-keywords,
.mcp-url,
.mcp-error-cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mcp-mono {
  font-family: "JetBrains Mono", "Cascadia Mono", Consolas, monospace;
  font-size: 12px;
}

.mcp-keywords,
.mcp-url,
.mcp-error-cell {
  color: #40506b;
}

@media (max-width: 1100px) {
  .mcp-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
