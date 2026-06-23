<script setup lang="ts">
import { computed, shallowRef } from "vue";
import MarkdownIt from "markdown-it";

import type { ChatMessage } from "../../composables/useRetriFlowChat";
import type { ChatMcpCallItem, ChatSourceItem, ChatWorkflow } from "../../services/api";

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
}>();

const defaultVisibleSourceCount = 3;
const sourcesExpanded = shallowRef(false);
const mcpExpanded = shallowRef(true);
const expandedSourceKey = shallowRef<string | null>(null);

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

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: false,
  typographer: false
});

const defaultLinkOpen =
  markdown.renderer.rules.link_open ||
  ((tokens, index, options, _env, self) => self.renderToken(tokens, index, options));
markdown.renderer.rules.link_open = (tokens, index, options, env, self) => {
  const token = tokens[index];
  const hrefIndex = token.attrIndex("href");
  if (hrefIndex >= 0) {
    const href = token.attrs?.[hrefIndex]?.[1] ?? "";
    if (!isSafeUrl(href)) {
      token.attrSet("href", "#");
    }
  }
  token.attrSet("target", "_blank");
  token.attrSet("rel", "noopener noreferrer");
  return defaultLinkOpen(tokens, index, options, env, self);
};

function isSafeUrl(value: string): boolean {
  return /^(https?:\/\/|\/)/i.test(value.trim());
}

function normalizeMessage(value: string): string {
  const normalized = value
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\u00a0/g, " ")
    .replace(/\|\s*\|(?=\s*-{3,})/g, "|\n|")
    .replace(/\|\s*(?=\|\s*[^|\n]+?\s*\|)/g, "|\n")
    .replace(/([。！？；，]\s*)([-*+]\s+\*\*?)/g, "$1\n\n$2")
    .replace(/([。！？；，]\s*)([-*+]\s+)/g, "$1\n\n$2")
    .replace(/([。！？；]\s*)(\d+\.\s+)/g, "$1\n\n$2")
    .replace(/(\[[0-9]+\]\s*)([-*+]\s+)/g, "$1\n\n$2")
    .replace(/([^\n])\s+(#{1,6}\s+)/g, "$1\n\n$2")
    .replace(/\n{4,}/g, "\n\n\n")
    .replace(/(^|\n)---(?=#{1,6}\s)/g, "$1---\n")
    .trim();
  return normalizeInlineMarkdownTables(normalized);
}

function isTableSeparatorLine(line: string): boolean {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line.trim());
}

function normalizeInlineMarkdownTables(value: string): string {
  const lines = value.split("\n");
  const normalizedLines: string[] = [];
  for (const rawLine of lines) {
    normalizedLines.push(...splitInlineTableSegments(rawLine));
  }
  return normalizedLines.join("\n");
}

function splitInlineTableSegments(rawLine: string): string[] {
  const line = rawLine.trim();
  if (!line.includes("|")) {
    return [rawLine];
  }

  const titledHeaderMatch = line.match(/^(.+?[:：])\s*(\|?\s*日期\s*\|\s*天气\s*\|\s*温度\s*\|\s*湿度\s*\|\s*风向\s*\|?.*)$/);
  if (titledHeaderMatch) {
    return [titledHeaderMatch[1].trim(), ...splitInlineTableSegments(titledHeaderMatch[2].trim())].filter(Boolean);
  }

  const doublePipeIndex = line.indexOf("||");
  if (doublePipeIndex >= 0) {
    const before = line.slice(0, doublePipeIndex).trim();
    const after = line.slice(doublePipeIndex + 1).trim();
    return [before, ...splitInlineTableSegments(after)].filter(Boolean);
  }

  if (!isDenseTableLine(line)) {
    return [rawLine];
  }

  const cells = line
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim())
    .filter(Boolean);
  if (cells.length < 6 || cells.length % 5 !== 0) {
    return [rawLine];
  }

  const rows: string[] = [];
  for (let index = 0; index < cells.length; index += 5) {
    rows.push(`| ${cells.slice(index, index + 5).join(" | ")} |`);
  }
  return rows;
}

function isDenseTableLine(line: string): boolean {
  const pipeCount = (line.match(/\|/g) ?? []).length;
  return pipeCount >= 8 && !isTableSeparatorLine(line);
}

function renderMessageHtml(value: string): string {
  const normalized = normalizeMessage(value || "正在等待模型返回...");
  return markdown.render(normalized).replace(/\[(\d+)\]/g, '<span class="citation">[$1]</span>');
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
        <div class="prose-message" v-html="renderMessageHtml(message.content)"></div>
        <div v-if="message.state === 'streaming'" class="streaming-caret"></div>
        <div v-if="message.state === 'error'" class="error-badge">回复失败</div>
        <div v-if="canRateMessage(message)" class="message-feedback">
          <button
            class="feedback-button"
            :class="{ active: message.feedbackVote === 1 }"
            :disabled="message.feedbackState === 'saving'"
            type="button"
            title="有帮助"
            @click="emit('feedback', message, 1)"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 10v11" /><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h3.28a2 2 0 0 0 1.7-.94L13 2a3.13 3.13 0 0 1 2 3.88Z" /></svg>
          </button>
          <button
            class="feedback-button"
            :class="{ active: message.feedbackVote === -1 }"
            :disabled="message.feedbackState === 'saving'"
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
    <div v-if="latestSources.length > 0" class="message-row assistant">
      <div class="avatar assistant-avatar" style="visibility: hidden;"></div>
      <div class="message-content references-panel">
         <div class="ref-header" @click="sourcesExpanded = !sourcesExpanded">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
            <span>参考了 {{ latestSources.length }} 个来源</span>
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
  background: var(--sidebar-dark-bg);
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

.message-feedback {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
}

.feedback-button {
  width: 28px;
  height: 28px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: white;
  color: var(--text-light);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.feedback-button:hover:not(:disabled),
.feedback-button.active {
  background: rgba(49, 94, 251, 0.08);
  border-color: rgba(49, 94, 251, 0.28);
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
  background: white;
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
  border-color: rgba(37, 99, 235, 0.28);
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
  background: rgba(37, 99, 235, 0.1);
  color: var(--primary);
  font-size: 11px;
  font-weight: 600;
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

