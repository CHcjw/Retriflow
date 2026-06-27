<script setup lang="ts">
import { computed, shallowRef } from "vue";
import type { ChatMessage } from "../../composables/useRetriFlowChat";
import type { ChatMcpCallItem, ChatMcpSourceItem, ChatSourceItem, ChatWorkflow } from "../../services/chatApi";
import { renderMessageHtml } from "../../utils/markdownRenderer";

const props = defineProps<{
  errorMessage: string;
  hasMessages: boolean;
  latestMcpCalls: ChatMcpCallItem[];
  latestSources: ChatSourceItem[];
  latestWorkflow: ChatWorkflow | null;
  loading: boolean;
  messages: ChatMessage[];
  statusText: string;
}>();

const emit = defineEmits<{
  feedback: [message: ChatMessage, vote: 1 | -1];
  regenerate: [];
}>();

const defaultVisibleSourceCount = 3;
const sourcesExpanded = shallowRef(false);
const mcpExpanded = shallowRef(true);
const thinkingExpanded = shallowRef(true);
const expandedSourceKey = shallowRef<string | null>(null);
const copiedMessageId = shallowRef<string | null>(null);

const sourceToggleLabel = computed(() => {
  if (props.latestSources.length <= defaultVisibleSourceCount) {
    return "已显示全部";
  }
  return sourcesExpanded.value ? "收起来源" : "展开全部";
});

const mcpToggleLabel = computed(() => (mcpExpanded.value ? "收起调用链" : "展开调用链"));
const visibleSources = computed(() =>
  sourcesExpanded.value ? props.latestSources : props.latestSources.slice(0, defaultVisibleSourceCount)
);
const visibleMcpCalls = computed(() => (mcpExpanded.value ? props.latestMcpCalls : []));
const mcpSourceItems = computed(() => {
  const seen = new Set<string>();
  const items: ChatMcpSourceItem[] = [];
  for (const call of props.latestMcpCalls) {
    for (const source of call.sources ?? []) {
      const url = String(source.url ?? "").trim();
      if (!url || seen.has(url)) {
        continue;
      }
      seen.add(url);
      items.push({
        title: String(source.title || url),
        url,
        snippet: source.snippet
      });
    }
  }
  return items;
});
const totalReferenceCount = computed(() => props.latestSources.length + mcpSourceItems.value.length);
function messageThinkingDurationSeconds(message: ChatMessage): number {
  if (!message.thinkingStartedAt) {
    return 0;
  }
  const end = message.thinkingEndedAt ?? Date.now();
  return Math.max(1, Math.round((end - message.thinkingStartedAt) / 1000));
}

function messageThinkingTitle(message: ChatMessage): string {
  if (message.thinkingState === "streaming") {
    return "正在思考";
  }
  const duration = messageThinkingDurationSeconds(message);
  return duration > 0 ? `已思考（用时 ${duration} 秒）` : "已思考";
}

function messageThinkingLines(message: ChatMessage): string[] {
  return (message.thinkingContent ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

const thinkingDurationSeconds = computed(() => {
  const workflow = props.latestWorkflow;
  if (!workflow?.deep_thinking || !workflow.retrieval_stage_metrics) {
    return 0;
  }
  let totalMs = 0;
  for (const metrics of Object.values(workflow.retrieval_stage_metrics)) {
    for (const key of ["duration_ms", "elapsed_ms", "latency_ms"]) {
      const value = metrics[key];
      if (typeof value === "number" && Number.isFinite(value)) {
        totalMs += value;
        break;
      }
    }
  }
  return totalMs > 0 ? Math.max(1, Math.round(totalMs / 1000)) : 0;
});
const thinkingTitle = computed(() => {
  if (!props.latestWorkflow?.deep_thinking) {
    return "";
  }
  return thinkingDurationSeconds.value > 0 ? `已思考（用时 ${thinkingDurationSeconds.value} 秒）` : "已思考";
});
const thinkingSummary = computed(() => {
  const workflow = props.latestWorkflow;
  if (!workflow?.deep_thinking) {
    return [];
  }
  const lines: string[] = [];

  const stageLabels: Record<string, string> = {
    local: "本地规则",
    memory: "读取会话记忆",
    rewrite: "问题重写/拆分",
    intent: "意图识别",
    route: "知识库/工具路由",
    retrieval: "知识检索",
    mcp: "MCP 工具调用",
    generation: "组织并生成回答"
  };

  const readableStages = (workflow.pipeline_stages ?? []).map((stage) => stageLabels[stage] ?? stage);
  if (readableStages.length > 0) {
    lines.push(`我先按 ${readableStages.join(" → ")} 的顺序处理这个问题。`);
  }
  if (workflow.rewritten_queries?.length > 0) {
    lines.push(`问题重写/拆分后得到：${workflow.rewritten_queries.join("；")}。`);
  }
  if (workflow.intent) {
    const confidence =
      workflow.intent_confidence !== undefined ? `，置信度 ${workflow.intent_confidence.toFixed(2)}` : "";
    lines.push(`意图识别为 ${workflow.intent}${confidence}。${workflow.intent_reason ? `依据：${workflow.intent_reason}` : ""}`);
  }
  if (workflow.route_mode) {
    const confidence =
      workflow.route_confidence !== undefined ? `，路由置信度 ${workflow.route_confidence.toFixed(2)}` : "";
    lines.push(`路由模式是 ${workflow.route_mode}${confidence}。`);
  }
  if (workflow.retrieval_count > 0) {
    lines.push(`知识库检索命中 ${workflow.retrieval_count} 个片段，使用 ${workflow.retrieval_channels.join(" / ")} 等通道。`);
  } else {
    lines.push("知识库没有命中可直接引用的片段。");
  }
  if (workflow.mcp_tool_count > 0) {
    lines.push(`同时调用了 ${workflow.mcp_tool_count} 个 MCP 工具补充实时或外部信息。`);
  }
  lines.push(workflow.smart_search ? "最后结合知识库、工具结果与当前问题生成回答。" : "最后结合可用上下文生成回答。");
  return lines;
});
const latestAssistantMessageId = computed(() => {
  return [...props.messages].reverse().find((message) => message.role === "assistant")?.id ?? "";
});

function shouldShowThinking(message: ChatMessage): boolean {
  return (
    message.role === "assistant" &&
    (Boolean(message.thinkingContent?.trim()) ||
      (message.id === latestAssistantMessageId.value && thinkingSummary.value.length > 0))
  );
}

function formatArguments(argumentsValue: Record<string, unknown>): string {
  return JSON.stringify(argumentsValue, null, 2);
}

function formatSourceLabel(source: ChatSourceItem): string {
  const chunkLabel = source.chunk_id < 0 ? "统计线索" : `Chunk ${source.chunk_id}`;
  return `文档 ${source.document_id} · ${chunkLabel}`;
}

function formatSourceScore(source: ChatSourceItem): string {
  if (!Number.isFinite(source.score)) {
    return "";
  }
  return `相关度 ${source.score.toFixed(3)}`;
}

function sourceIdentity(source: ChatSourceItem, index = 0): string {
  return `${source.knowledge_base_id}:${source.document_id}:${source.chunk_id}:${index}`;
}

function isSourceExpanded(source: ChatSourceItem, index = 0): boolean {
  return expandedSourceKey.value === sourceIdentity(source, index);
}

function toggleSourceDetail(source: ChatSourceItem, index = 0) {
  expandedSourceKey.value = isSourceExpanded(source, index) ? null : sourceIdentity(source, index);
}

function openSourceLink(source: ChatSourceItem) {
  if (!source.source_link) {
    return;
  }
  window.open(source.source_link, "_blank", "noopener,noreferrer");
}

function openMcpSource(source: ChatMcpSourceItem) {
  if (!source.url) {
    return;
  }
  window.open(source.url, "_blank", "noopener,noreferrer");
}

function canRateMessage(message: ChatMessage): boolean {
  return message.role === "assistant" && message.state === "complete" && Boolean(message.backendId);
}

function buildSourcePreview(content: string): string {
  const normalized = content.replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "该来源暂无可预览摘要，可展开查看完整片段。";
  }
  if (normalized.length <= 120) {
    return normalized;
  }
  return `${normalized.slice(0, 120)}...`;
}

async function copyMessage(message: ChatMessage) {
  if (!message.content.trim()) {
    return;
  }
  await navigator.clipboard?.writeText(message.content);
  copiedMessageId.value = message.id;
  window.setTimeout(() => {
    if (copiedMessageId.value === message.id) {
      copiedMessageId.value = null;
    }
  }, 1400);
}

function canUseAssistantActions(message: ChatMessage): boolean {
  return message.role === "assistant" && message.state === "complete" && Boolean(message.content.trim());
}
</script>

<template>
  <div class="chat-transcript">
    <div
      v-for="message in messages"
      :key="message.id"
      class="message-row"
      :class="message.role"
    >
      <div v-if="message.role === 'assistant'" class="avatar assistant-avatar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a2 2 0 012 2v2h4a2 2 0 012 2v10a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2h4V4a2 2 0 012-2zm0 8a2 2 0 100 4 2 2 0 000-4z" /></svg>
      </div>

      <div class="message-content" :class="{ 'bubble': message.role === 'user' }">
        <div
          v-if="shouldShowThinking(message)"
          class="thinking-panel"
        >
          <button class="thinking-header" type="button" @click="thinkingExpanded = !thinkingExpanded">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            <span>{{ message.thinkingContent ? messageThinkingTitle(message) : thinkingTitle }}</span>
            <svg class="chevron" :class="{ open: thinkingExpanded }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <div v-if="thinkingExpanded" class="thinking-body">
            <p v-for="(line, index) in (message.thinkingContent ? messageThinkingLines(message) : thinkingSummary)" :key="`${line}-${index}`">{{ line }}</p>
          </div>
        </div>
        <div class="prose-message" v-html="renderMessageHtml(message.content)"></div>
        <div v-if="message.state === 'streaming'" class="streaming-caret"></div>
        <div v-if="message.state === 'error'" class="error-badge">回复失败</div>
        <div v-if="canUseAssistantActions(message)" class="message-actions">
          <button
            class="feedback-button"
            type="button"
            :title="copiedMessageId === message.id ? '已复制' : '复制'"
            @click="copyMessage(message)"
          >
            <svg v-if="copiedMessageId !== message.id" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" />
              <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20 6L9 17l-5-5" />
            </svg>
          </button>
          <button
            class="feedback-button"
            type="button"
            title="重新生成"
            :disabled="loading"
            @click="emit('regenerate')"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 12a9 9 0 11-2.64-6.36" />
              <path d="M21 3v6h-6" />
            </svg>
          </button>
          <button
            class="feedback-button"
            :class="{ active: message.feedbackVote === 1 }"
            :disabled="message.feedbackState === 'saving' || !canRateMessage(message)"
            type="button"
            title="有帮助"
            @click="emit('feedback', message, 1)"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 10v11" /><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h3.28a2 2 0 0 0 1.7-.94L13 2a3.13 3.13 0 0 1 2 3.88Z" /></svg>
          </button>
          <button
            class="feedback-button"
            :class="{ active: message.feedbackVote === -1 }"
            :disabled="message.feedbackState === 'saving' || !canRateMessage(message)"
            type="button"
            title="不准确"
            @click="emit('feedback', message, -1)"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 14V3" /><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-3.28a2 2 0 0 0-1.7.94L11 22a3.13 3.13 0 0 1-2-3.88Z" /></svg>
          </button>
          <span v-if="message.feedbackState === 'saved'" class="feedback-status">已记录</span>
          <span v-else-if="message.feedbackState === 'error'" class="feedback-status error">失败</span>
        </div>
      </div>
    </div>

    <!-- Reference & Source panels here as needed, simplified for aesthetic -->
    <div v-if="totalReferenceCount > 0" class="message-row assistant">
      <div class="avatar assistant-avatar" style="visibility: hidden;"></div>
      <div class="message-content references-panel">
         <div class="ref-header" @click="sourcesExpanded = !sourcesExpanded">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
            <span>参考了 {{ totalReferenceCount }} 个来源</span>
            <svg class="chevron" :class="{'open': sourcesExpanded}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 9l-7 7-7-7" /></svg>
         </div>
         <div v-if="sourcesExpanded" class="ref-list">
            <div
              v-for="(source, index) in visibleSources"
              :key="sourceIdentity(source, index)"
              class="ref-item"
              :class="{ expanded: isSourceExpanded(source, index) }"
              role="button"
              tabindex="0"
              @click="toggleSourceDetail(source, index)"
              @keydown.enter.prevent="toggleSourceDetail(source, index)"
              @keydown.space.prevent="toggleSourceDetail(source, index)"
            >
               <div class="ref-title-row">
                 <span class="ref-index">[{{index + 1}}]</span>
                 <span class="ref-title">{{ source.document_title }}</span>
                 <span v-if="source.chunk_id < 0" class="ref-badge">统计</span>
               </div>
               <div class="ref-meta">
                 <span>{{ formatSourceLabel(source) }}</span>
                 <span v-if="formatSourceScore(source)">{{ formatSourceScore(source) }}</span>
               </div>
               <div class="ref-preview">{{ buildSourcePreview(source.content) }}</div>
               <div v-if="isSourceExpanded(source, index)" class="ref-detail">{{ source.content || "该来源暂无完整片段。" }}</div>
               <button
                 v-if="source.source_link"
                 class="ref-open"
                 type="button"
                 @click.stop="openSourceLink(source)"
               >
                 打开原文
               </button>
            </div>
            <div
              v-for="(source, index) in mcpSourceItems"
              :key="source.url"
              class="ref-item web-ref-item"
              role="button"
              tabindex="0"
              @click="openMcpSource(source)"
              @keydown.enter.prevent="openMcpSource(source)"
              @keydown.space.prevent="openMcpSource(source)"
            >
              <div class="ref-title-row">
                <span class="ref-index">[W{{ index + 1 }}]</span>
                <span class="ref-title">{{ source.title }}</span>
                <span class="ref-badge web">联网</span>
              </div>
              <div class="ref-meta">
                <span class="ref-url">{{ source.url }}</span>
              </div>
              <div v-if="source.snippet" class="ref-preview">{{ source.snippet }}</div>
            </div>
         </div>
      </div>
    </div>

    <div v-if="statusText || errorMessage" class="status-indicator">
      <div class="typing-indicator">
        <span></span><span></span><span></span>
      </div>
      <span class="status-text">{{ errorMessage || statusText }}</span>
    </div>
  </div>
</template>

<style>
/* Global unscoped styles for v-html rendered prose content */
.prose-message {
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-main);
  word-wrap: break-word;
}

.prose-message p {
  margin-bottom: 16px;
}
.prose-message p:last-child {
  margin-bottom: 0;
}

.prose-message h1, .prose-message h2, .prose-message h3, .prose-message h4, .prose-message h5, .prose-message h6 {
  font-weight: 700;
  color: var(--text-main);
  margin-top: 24px;
  margin-bottom: 12px;
}
.prose-message h1 { font-size: 20px; }
.prose-message h2 { font-size: 18px; }
.prose-message h3 { font-size: 16px; }
.prose-message h4, .prose-message h5, .prose-message h6 { font-size: 15px; }

.prose-message ul, .prose-message ol {
  padding-left: 20px;
  margin-bottom: 16px;
}

.prose-message li {
  margin-bottom: 8px;
}

.prose-message li::marker {
  color: var(--text-light);
}

.prose-message a {
  color: var(--primary);
  font-weight: 600;
  text-decoration: none;
}

.prose-message a:hover {
  text-decoration: underline;
}

.prose-message blockquote {
  margin: 14px 0;
  padding: 12px 16px;
  border-left: 3px solid var(--primary);
  border-radius: 10px;
  background: var(--sidebar-bg);
  color: var(--text-muted);
}

.prose-message blockquote p {
  margin-bottom: 8px;
}

.prose-message hr {
  border: 0;
  border-top: 1px solid var(--border-light);
  margin: 20px 0;
}

.prose-message table {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  overflow: hidden;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  display: block;
  max-width: 100%;
  overflow-x: auto;
}

.prose-message th,
.prose-message td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-light);
  border-right: 1px solid var(--border-light);
  text-align: left;
  white-space: nowrap;
}

.prose-message th {
  background: var(--sidebar-bg);
  font-weight: 700;
}

.prose-message .citation {
  display: inline-flex;
  align-items: center;
  margin: 0 2px;
  color: var(--primary);
  font-weight: 700;
}

.prose-message strong {
  font-weight: 600;
  color: var(--text-main);
}

.prose-message em {
  font-style: italic;
}

.prose-message code {
  background: var(--sidebar-bg);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 13px;
  color: var(--primary);
}

.prose-message pre {
  background: #14202a;
  padding: 16px;
  border-radius: 12px;
  overflow-x: auto;
  margin-bottom: 16px;
}

.prose-message pre code {
  background: none;
  padding: 0;
  color: #E2E8F0;
  font-size: 14px;
}

.prose-message .message-image {
  max-width: 100%;
  border-radius: 12px;
  margin: 16px 0;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
}
</style>

<style scoped>
.chat-transcript {
  display: flex;
  flex-direction: column;
  gap: 32px;
  padding-top: 24px;
}

.message-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  width: 100%;
}

.message-row.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.assistant-avatar {
  background: var(--primary);
  color: white;
}
.assistant-avatar svg {
  width: 20px;
  height: 20px;
}

.message-content {
  max-width: 85%;
}

.message-content.bubble {
  background: var(--sidebar-bg);
  padding: 12px 20px;
  border-radius: 20px;
  border-top-right-radius: 4px;
  color: var(--text-main);
}

.streaming-caret {
  display: inline-block;
  width: 8px;
  height: 16px;
  background: var(--primary);
  animation: blink 1s step-end infinite;
  vertical-align: middle;
  margin-left: 4px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.error-badge {
  display: inline-block;
  margin-top: 8px;
  padding: 4px 8px;
  background: rgba(239, 68, 68, 0.1);
  color: var(--danger);
  border-radius: 4px;
  font-size: 12px;
}

.message-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
}

.feedback-button {
  width: 28px;
  height: 28px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--surface-strong);
  color: var(--text-light);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.feedback-button:hover:not(:disabled),
.feedback-button.active {
  background: rgba(15, 143, 130, 0.08);
  border-color: rgba(15, 143, 130, 0.28);
  color: var(--primary);
}

.feedback-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.feedback-button svg {
  width: 15px;
  height: 15px;
}

.feedback-status {
  font-size: 12px;
  color: var(--text-light);
}

.feedback-status.error {
  color: var(--danger);
}

.references-panel {
  width: 100%;
  max-width: 600px;
}

.thinking-panel {
  width: 100%;
  max-width: 720px;
  color: #667085;
}

.thinking-header {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  color: #475467;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.thinking-header svg {
  width: 16px;
  height: 16px;
}

.thinking-header .chevron {
  width: 14px;
  height: 14px;
  margin-left: 2px;
}

.thinking-body {
  margin-top: 12px;
  margin-left: 8px;
  padding-left: 18px;
  border-left: 1px solid #e4e7ec;
  color: #667085;
  line-height: 1.8;
  font-size: 14px;
}

.thinking-body p {
  margin: 0 0 12px;
}

.thinking-body p:last-child {
  margin-bottom: 0;
}

.ref-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: white;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  cursor: pointer;
  color: var(--text-muted);
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.ref-header:hover {
  background: var(--sidebar-bg);
}

.ref-header svg {
  width: 16px;
  height: 16px;
}

.chevron {
  margin-left: auto;
  transition: transform 0.2s;
}

.chevron.open {
  transform: rotate(180deg);
}

.ref-list {
  margin-top: 8px;
  padding: 10px;
  background: var(--sidebar-bg);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ref-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-main);
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.ref-item:hover,
.ref-item:focus-visible,
.ref-item.expanded {
  border-color: rgba(15, 143, 130, 0.3);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
  outline: none;
}

.ref-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.ref-index {
  color: var(--primary);
  font-weight: 600;
  flex: 0 0 auto;
}

.ref-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}

.ref-badge {
  flex: 0 0 auto;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(15, 143, 130, 0.11);
  color: var(--primary);
  font-size: 11px;
  font-weight: 600;
}

.ref-badge.web {
  background: rgba(16, 185, 129, 0.12);
  color: #059669;
}

.web-ref-item {
  cursor: pointer;
}

.ref-url {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--primary);
}

.ref-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  color: var(--text-light);
  font-size: 12px;
  line-height: 1.4;
}

.ref-preview,
.ref-detail {
  color: var(--text-muted);
  line-height: 1.55;
  word-break: break-word;
}

.ref-preview {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.ref-detail {
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px dashed var(--border-light);
  color: var(--text-main);
  white-space: pre-wrap;
}

.ref-open {
  align-self: flex-start;
  margin-top: 2px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  align-self: flex-start;
  color: var(--text-light);
  font-size: 13px;
}

.typing-indicator {
  display: flex;
  gap: 4px;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  background: var(--text-light);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
</style>


