<script setup lang="ts">
import type { AdminIntentNodeItem } from "../../../services/adminApi";
import AdminTablePagination from "../common/AdminTablePagination.vue";

export type AdminIntentRow = AdminIntentNodeItem & {
  type: string;
  path: string;
  resource: string;
  sampleCount: number;
  status: string;
};

const intentMode = defineModel<"list" | "tree">("intentMode", { required: true });
const intentSearch = defineModel<string>("intentSearch", { required: true });
const selectedIntentNodeId = defineModel<string>("selectedIntentNodeId", { required: true });
const realIntentPage = defineModel<number>("realIntentPage", { required: true });

defineProps<{
  adminIntentNodeCount: number;
  childIntentNodes: (parentId: string) => AdminIntentNodeItem[];
  intentNodeLevelClass: (level: string) => string;
  intentNodeTypeClass: (type: string) => string;
  pagedRealIntentRows: AdminIntentRow[];
  realIntentRowsTotal: number;
  rootIntentNodes: AdminIntentNodeItem[];
  selectedIntentNode: AdminIntentNodeItem | null;
  tablePageSize: number;
}>();

const emit = defineEmits<{
  create: [];
  createChild: [parentId: string];
  delete: [nodeId: string];
  edit: [nodeId: string];
  refresh: [];
}>();
</script>

<template>
  <div class="page-head">
    <div>
      <h1>意图管理</h1>
      <p>维护意图树、意图列表和节点路由配置，数据持久化在后端 admin_intent_nodes 表。</p>
    </div>
    <div class="page-actions">
      <div class="segmented-tabs">
        <button :class="{ active: intentMode === 'tree' }" type="button" @click="intentMode = 'tree'">意图树配置</button>
        <button :class="{ active: intentMode === 'list' }" type="button" @click="intentMode = 'list'">意图列表</button>
      </div>
      <button class="ghost-btn" type="button" @click="emit('refresh')">刷新</button>
      <button class="primary-btn" type="button" @click="emit('create')">新建意图节点</button>
    </div>
  </div>

  <section v-if="intentMode === 'tree'" class="admin-grid-two">
    <article class="task-card intent-tree-panel">
      <div class="table-toolbar">
        <div>
          <h2>意图树配置</h2>
          <p>点击节点查看详情，支持新增子节点、编辑与删除。</p>
        </div>
      </div>
      <div class="intent-tree-box real-tree">
        <div v-for="node in rootIntentNodes" :key="node.id" class="intent-tree-group">
          <button
            class="intent-node root-node tree-button"
            :class="{ active: selectedIntentNode?.id === node.id }"
            type="button"
            @click="selectedIntentNodeId = node.id"
          >
            <strong>{{ node.name }}</strong>
            <span class="intent-tag-row">
              <i class="intent-tag" :class="intentNodeLevelClass(node.level)">{{ node.level }}</i>
              <i class="intent-tag" :class="intentNodeTypeClass(node.node_type)">{{ node.node_type }}</i>
              <i class="intent-tag" :class="{ disabled: !node.enabled }">{{ node.enabled ? "启用" : "停用" }}</i>
            </span>
          </button>
          <div v-if="childIntentNodes(node.id).length > 0" class="intent-child-list">
            <button
              v-for="child in childIntentNodes(node.id)"
              :key="child.id"
              class="intent-node child-node tree-button"
              :class="{ active: selectedIntentNode?.id === child.id }"
              type="button"
              @click="selectedIntentNodeId = child.id"
            >
              <strong>{{ child.name }}</strong>
              <span class="intent-tag-row">
                <i class="intent-tag" :class="intentNodeLevelClass(child.level)">{{ child.level }}</i>
                <i class="intent-tag" :class="intentNodeTypeClass(child.node_type)">{{ child.node_type }}</i>
                <i class="intent-parent-label">{{ node.name }}</i>
              </span>
            </button>
          </div>
        </div>
        <div v-if="adminIntentNodeCount === 0" class="empty-cell">暂无意图节点，请点击右上角新建。</div>
      </div>
    </article>

    <article class="task-card intent-detail-card">
      <template v-if="selectedIntentNode">
        <div class="intent-detail-head">
          <div>
            <h2>{{ selectedIntentNode.name }}</h2>
            <div class="intent-detail-meta">
              <span>{{ selectedIntentNode.code }}</span>
              <i class="intent-tag" :class="intentNodeLevelClass(selectedIntentNode.level)">{{ selectedIntentNode.level }}</i>
              <i class="intent-tag" :class="intentNodeTypeClass(selectedIntentNode.node_type)">{{ selectedIntentNode.node_type }}</i>
            </div>
          </div>
          <span class="status-pill" :class="{ success: selectedIntentNode.enabled, warning: !selectedIntentNode.enabled }">
            {{ selectedIntentNode.enabled ? "启用" : "停用" }}
          </span>
        </div>
        <dl class="setting-list">
          <dt>父节点</dt>
          <dd>{{ selectedIntentNode.parent_id }}</dd>
          <dt>知识库</dt>
          <dd>
            <i v-if="selectedIntentNode.knowledge_base_id" class="intent-tag type-kb">{{ selectedIntentNode.knowledge_base_id }}</i>
            <span v-else>-</span>
          </dd>
          <dt>MCP 工具</dt>
          <dd>
            <i v-if="selectedIntentNode.mcp_tool_id" class="intent-tag type-mcp">{{ selectedIntentNode.mcp_tool_id }}</i>
            <span v-else>-</span>
          </dd>
          <dt>Collection</dt>
          <dd>{{ selectedIntentNode.collection_name || "-" }}</dd>
          <dt>TopK</dt>
          <dd>{{ selectedIntentNode.top_k ?? "默认" }}</dd>
          <dt>MinScore</dt>
          <dd>{{ selectedIntentNode.min_score ?? "默认" }}</dd>
          <dt>排序</dt>
          <dd>{{ selectedIntentNode.sort_order }}</dd>
          <dt>描述</dt>
          <dd>{{ selectedIntentNode.description || "-" }}</dd>
          <dt>规则片段</dt>
          <dd>{{ selectedIntentNode.rule_snippet || "-" }}</dd>
          <dt>参数 Prompt</dt>
          <dd>
            <i v-if="selectedIntentNode.param_prompt_template" class="intent-tag type-mcp">已配置</i>
            <span v-else>-</span>
          </dd>
        </dl>
        <div class="tag-row">
          <span v-for="question in selectedIntentNode.sample_questions" :key="question" class="soft-tag">{{ question }}</span>
          <span v-if="selectedIntentNode.sample_questions.length === 0" class="muted-line">暂无示例问题</span>
        </div>
        <div class="page-actions section-gap">
          <button class="ghost-btn" type="button" @click="emit('createChild', selectedIntentNode.id)">新增子节点</button>
          <button class="ghost-btn" type="button" @click="emit('edit', selectedIntentNode.id)">编辑节点</button>
          <button class="danger-btn" type="button" @click="emit('delete', selectedIntentNode.id)">删除节点</button>
        </div>
      </template>
      <div v-else class="empty-cell">请选择一个意图节点。</div>
    </article>
  </section>

  <section v-else class="table-card section-gap">
    <div class="table-toolbar">
      <div>
        <h2>意图列表</h2>
        <p>按节点名称、编码或 ID 搜索；点击“定位树”可跳转到意图树对应节点。</p>
      </div>
      <div class="toolbar-actions">
        <input v-model="intentSearch" class="ui-input" type="text" placeholder="搜索意图名称 / Code / ID" />
        <button class="ghost-btn" type="button" @click="intentSearch = ''">清空筛选</button>
      </div>
    </div>
    <div class="table-scroll">
      <table class="data-table intent-table">
        <thead>
          <tr>
            <th>意图节点</th>
            <th>层级</th>
            <th>类型</th>
            <th>路径</th>
            <th>关联资源</th>
            <th>示例数</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in pagedRealIntentRows" :key="item.id">
            <td>
              <strong>{{ item.name }}</strong>
              <p class="muted-line">{{ item.code }} · {{ item.id }}</p>
            </td>
            <td><span class="badge">{{ item.level }}</span></td>
            <td>{{ item.type }}</td>
            <td>{{ item.path }}</td>
            <td>{{ item.resource }}</td>
            <td>{{ item.sampleCount }}</td>
            <td><span class="status-pill" :class="{ success: item.enabled, warning: !item.enabled }">{{ item.status }}</span></td>
            <td class="table-actions-cell">
              <button class="ghost-btn compact" type="button" @click="selectedIntentNodeId = item.id; intentMode = 'tree'">定位树</button>
              <button class="ghost-btn compact" type="button" @click="emit('edit', item.id)">修改</button>
            </td>
          </tr>
          <tr v-if="realIntentRowsTotal === 0">
            <td colspan="8" class="empty-cell">暂无意图节点。</td>
          </tr>
        </tbody>
      </table>
    </div>
    <AdminTablePagination :page="realIntentPage" :page-size="tablePageSize" :total="realIntentRowsTotal" @change="realIntentPage = $event" />
  </section>
</template>

<style scoped>
.admin-grid-two {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.task-card {
  border: 1px solid #dbe4f0;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(34, 43, 63, 0.05);
  padding: 28px;
}

.task-card h2 {
  margin: 0;
  color: #172033;
  font-size: 18px;
}

.segmented-tabs {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border: 1px solid #dbe4f0;
  border-radius: 14px;
  background: #f6f9fc;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.segmented-tabs button {
  min-height: 38px;
  border: 0;
  border-radius: 10px;
  padding: 0 16px;
  background: transparent;
  color: #51627a;
  font-weight: 800;
  white-space: nowrap;
  cursor: pointer;
}

.segmented-tabs button.active {
  background: #ffffff;
  color: var(--primary);
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
}

.intent-tree-panel {
  padding: 0;
  overflow: hidden;
}

.intent-tree-box {
  display: grid;
  gap: 10px;
  padding: 16px;
}

.intent-tree-group {
  display: grid;
  gap: 8px;
}

.intent-node {
  display: grid;
  gap: 7px;
  width: 100%;
  border: 1px solid #dbe4f0;
  border-radius: 10px;
  padding: 12px;
  background: #fbfdff;
  color: #172033;
  text-align: left;
}

.intent-node.active {
  border-color: rgba(15, 143, 130, 0.55);
  background: #e8f6f3;
}

.child-node {
  margin-left: 24px;
  width: calc(100% - 24px);
}

.tree-button {
  cursor: pointer;
}

.intent-tag-row,
.intent-detail-meta,
.tag-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.intent-tag {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  border-radius: 999px;
  padding: 0 8px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
}

.intent-tag.level-domain {
  background: #e0f2fe;
  color: #0369a1;
}

.intent-tag.level-category {
  background: #dcfce7;
  color: #15803d;
}

.intent-tag.type-mcp {
  background: #eef2ff;
  color: #4338ca;
}

.intent-tag.type-system {
  background: #f1f5f9;
  color: #475569;
}

.intent-tag.type-kb {
  background: #edf7ff;
  color: #24557a;
}

.intent-tag.disabled {
  background: #f1f5f9;
  color: #64748b;
}

.intent-parent-label {
  color: #64748b;
  font-size: 12px;
  font-style: normal;
}

.intent-detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.setting-list {
  display: grid;
  grid-template-columns: minmax(90px, auto) minmax(0, 1fr);
  gap: 10px 14px;
}

.setting-list dt {
  color: #64748b;
  font-weight: 700;
}

.setting-list dd {
  margin: 0;
  color: #172033;
  word-break: break-word;
}

.soft-tag {
  border-radius: 999px;
  padding: 5px 10px;
  background: #f1f5f9;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
}

.muted-line {
  margin: 4px 0 0;
  color: #8794aa;
  font-size: 12px;
}

.section-gap {
  margin-top: 16px;
}

.table-actions-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
  min-width: 0;
}

@media (max-width: 1100px) {
  .admin-grid-two {
    grid-template-columns: 1fr;
  }
}
</style>
