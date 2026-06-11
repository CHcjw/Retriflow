<script setup lang="ts">
import { computed, shallowRef } from "vue";

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

const defaultVisibleSourceCount = 3;
const sourcesExpanded = shallowRef(false);
const mcpExpanded = shallowRef(true);
const expandedSourceChunkId = shallowRef<number | null>(null);

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
const urlPattern = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function normalizeMessage(value: string): string {
  return value
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{4,}/g, "\n\n\n")
    .replace(/(^|\n)---(?=#{1,6}\s)/g, "$1---\n")
    .trim();
}

function renderInlineMarkdown(value: string): string {
  const linkTokens: string[] = [];
  let escaped = escapeHtml(value);

  escaped = escaped.replace(urlPattern, (_, label: string, url: string) => {
    const token = `__RETRIFLOW_LINK_${linkTokens.length}__`;
    linkTokens.push(
      `<a href="${url}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`
    );
    return token;
  });

  escaped = escaped
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>")
    .replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "<em>$1</em>")
    .replace(/(?<!_)_([^_]+)_(?!_)/g, "<em>$1</em>")
    .replace(/\[(\d+)\]/g, '<span class="citation">[$1]</span>');

  return linkTokens.reduce(
    (html, tokenHtml, index) => html.replace(`__RETRIFLOW_LINK_${index}__`, tokenHtml),
    escaped
  );
}

function renderBlockquote(lines: string[]): string {
  const content = lines.map((line) => line.replace(/^>\s?/, "")).join("\n");
  return `<blockquote>${renderMessageHtml(content)}</blockquote>`;
}

function renderList(lines: string[], ordered: boolean): string {
  const tag = ordered ? "ol" : "ul";
  const itemPattern = ordered ? /^\d+\.\s+/ : /^[-*+]\s+/;
  const items = lines
    .map((line) => line.replace(itemPattern, "").trim())
    .filter(Boolean)
    .map((item) => `<li>${renderInlineMarkdown(item)}</li>`)
    .join("");
  return `<${tag}>${items}</${tag}>`;
}

function renderCodeBlock(lines: string[]): string {
  const code = escapeHtml(lines.join("\n"));
  return `<pre><code>${code}</code></pre>`;
}

function renderParagraph(lines: string[]): string {
  const content = lines.map((line) => renderInlineMarkdown(line)).join("<br>");
  return `<p>${content}</p>`;
}

function renderTable(lines: string[]): string {
  const rows = lines.map((line) =>
    line
      .trim()
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim())
  );
  const [header, , ...body] = rows;
  const headHtml = `<thead><tr>${header
    .map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`)
    .join("")}</tr></thead>`;
  const bodyHtml = body.length
    ? `<tbody>${body
        .map(
          (row) =>
            `<tr>${row.map((cell) => `<td>${renderInlineMarkdown(cell)}</td>`).join("")}</tr>`
        )
        .join("")}</tbody>`
    : "";
  return `<table>${headHtml}${bodyHtml}</table>`;
}

function renderMessageHtml(value: string): string {
  const normalized = normalizeMessage(value || "正在等待模型返回...");
  const lines = normalized.split("\n");
  const blocks: string[] = [];

  for (let index = 0; index < lines.length; ) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      index += 1;
      blocks.push(renderCodeBlock(codeLines));
      continue;
    }

    if (/^#{1,6}\s+/.test(trimmed)) {
      const level = Math.min(trimmed.match(/^#+/)?.[0].length ?? 1, 6);
      const content = trimmed.replace(/^#{1,6}\s+/, "");
      blocks.push(`<h${level}>${renderInlineMarkdown(content)}</h${level}>`);
      index += 1;
      continue;
    }

    if (/^---+$/.test(trimmed)) {
      blocks.push("<hr>");
      index += 1;
      continue;
    }

    if (trimmed.startsWith(">")) {
      const quoteLines: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith(">")) {
        quoteLines.push(lines[index].trim());
        index += 1;
      }
      blocks.push(renderBlockquote(quoteLines));
      continue;
    }

    if (/^[-*+]\s+/.test(trimmed)) {
      const listLines: string[] = [];
      while (index < lines.length && /^[-*+]\s+/.test(lines[index].trim())) {
        listLines.push(lines[index].trim());
        index += 1;
      }
      blocks.push(renderList(listLines, false));
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const listLines: string[] = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
        listLines.push(lines[index].trim());
        index += 1;
      }
      blocks.push(renderList(listLines, true));
      continue;
    }

    if (
      trimmed.includes("|") &&
      index + 1 < lines.length &&
      /^\s*\|?[:\- ]+\|[:\-| ]+\|?\s*$/.test(lines[index + 1].trim())
    ) {
      const tableLines = [trimmed, lines[index + 1].trim()];
      index += 2;
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        tableLines.push(lines[index].trim());
        index += 1;
      }
      blocks.push(renderTable(tableLines));
      continue;
    }

    const paragraphLines: string[] = [trimmed];
    index += 1;
    while (index < lines.length) {
      const nextTrimmed = lines[index].trim();
      if (
        !nextTrimmed ||
        nextTrimmed.startsWith("```") ||
        /^#{1,6}\s+/.test(nextTrimmed) ||
        /^---+$/.test(nextTrimmed) ||
        nextTrimmed.startsWith(">") ||
        /^[-*+]\s+/.test(nextTrimmed) ||
        /^\d+\.\s+/.test(nextTrimmed)
      ) {
        break;
      }
      paragraphLines.push(nextTrimmed);
      index += 1;
    }
    blocks.push(renderParagraph(paragraphLines));
  }

  return blocks.join("");
}

function formatArguments(argumentsValue: Record<string, unknown>): string {
  return JSON.stringify(argumentsValue, null, 2);
}

function formatSourceLabel(source: ChatSourceItem): string {
  return `知识库 ${source.knowledge_base_id} · 文档 ${source.document_id} · Chunk ${source.chunk_id}`;
}

function isSourceExpanded(source: ChatSourceItem): boolean {
  return expandedSourceChunkId.value === source.chunk_id;
}

function toggleSourceDetail(source: ChatSourceItem) {
  expandedSourceChunkId.value = isSourceExpanded(source) ? null : source.chunk_id;
}

function openSourceLink(source: ChatSourceItem) {
  if (!source.source_link) {
    return;
  }
  window.open(source.source_link, "_blank", "noopener,noreferrer");
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

const emptyStateTitle = computed(() => {
  if (!props.hasMessages) {
    return "当前会话还没有真实消息";
  }
  return "";
});
</script>

<template>
  <div class="chat-transcript">
    <div v-if="!hasMessages" class="empty-state-card">
      <strong>{{ emptyStateTitle }}</strong>
      <p class="status-copy">这里不会再显示本地占位消息。等你发出第一条问题后，真实问答记录会从数据库加载并展示在这里。</p>
    </div>

    <div
      v-for="message in messages"
      :key="message.id"
      class="message-card"
      :class="[message.role, `is-${message.state}`]"
    >
      <div class="pane-title-row">
        <strong>{{ message.role === "assistant" ? "RetriFlow" : "用户" }}</strong>
        <span v-if="message.state === 'streaming'" class="message-state-pill">正在回复</span>
        <span v-else-if="message.state === 'stopped'" class="message-state-pill muted">已停止</span>
        <span v-else-if="message.state === 'error'" class="message-state-pill error">失败</span>
      </div>
      <div class="message-body prose-message" v-html="renderMessageHtml(message.content)"></div>
      <div v-if="message.state === 'streaming'" class="streaming-inline-indicator" aria-hidden="true">
        <span class="streaming-caret">|</span>
      </div>
    </div>

    <section v-if="latestMcpCalls.length > 0" class="sources-panel">
      <div class="pane-title-row">
        <h3>本次工具调用</h3>
        <div class="inline-actions">
          <span class="status-copy">{{ latestMcpCalls.length }} 次</span>
          <button type="button" class="secondary-button compact-button" @click="mcpExpanded = !mcpExpanded">
            {{ mcpToggleLabel }}
          </button>
        </div>
      </div>
      <article v-for="(call, index) in visibleMcpCalls" :key="`${call.tool_id}-${index}`" class="message-card mcp-card">
        <div class="pane-title-row">
          <strong>{{ call.tool_id }}</strong>
          <span class="status-badge" :class="{ 'status-badge-error': call.is_error }">
            {{ call.is_error ? "错误" : "成功" }}
          </span>
        </div>
        <div class="mcp-detail-grid">
          <div>
            <p class="mcp-section-label">参数</p>
            <pre class="mcp-json-block">{{ formatArguments(call.arguments) }}</pre>
          </div>
          <div>
            <p class="mcp-section-label">结果摘要</p>
            <p class="mcp-result-copy">{{ call.content }}</p>
          </div>
        </div>
      </article>
    </section>

    <section v-if="latestSources.length > 0" class="sources-panel">
      <div class="pane-title-row">
        <h3>参考来源</h3>
        <div class="inline-actions">
          <span class="source-count-pill">{{ latestSources.length }} 条</span>
          <button
            type="button"
            class="secondary-button compact-button"
            :disabled="latestSources.length <= defaultVisibleSourceCount"
            @click="sourcesExpanded = !sourcesExpanded"
          >
            {{ sourceToggleLabel }}
          </button>
        </div>
      </div>
      <div v-if="visibleSources.length > 0" class="source-card-grid">
        <article v-for="(source, index) in visibleSources" :key="source.chunk_id" class="message-card source-card">
          <div class="pane-title-row source-card-header">
            <div class="source-heading">
              <span class="source-index-pill">来源 {{ index + 1 }}</span>
              <strong>{{ source.document_title }}</strong>
            </div>
            <span class="status-badge">score {{ source.score.toFixed(2) }}</span>
          </div>
          <p class="source-meta">{{ formatSourceLabel(source) }}</p>
          <p class="source-preview">{{ buildSourcePreview(source.content) }}</p>
          <div class="inline-actions source-detail-actions">
            <button
              type="button"
              class="secondary-button compact-button"
              @click="toggleSourceDetail(source)"
            >
              {{ isSourceExpanded(source) ? "收起详情" : "查看详情" }}
            </button>
            <button
              v-if="source.source_link"
              type="button"
              class="secondary-button compact-button"
              @click="openSourceLink(source)"
            >
              打开片段
            </button>
          </div>
          <div v-if="isSourceExpanded(source)" class="source-detail-panel">
            <div class="source-detail-grid">
              <div>
                <span class="workflow-label">文档标题</span>
                <p>{{ source.document_title }}</p>
              </div>
              <div>
                <span class="workflow-label">更新时间</span>
                <p>{{ source.source_updated_at || "暂无" }}</p>
              </div>
              <div>
                <span class="workflow-label">知识库 ID</span>
                <p>{{ source.knowledge_base_id }}</p>
              </div>
              <div>
                <span class="workflow-label">文档 ID</span>
                <p>{{ source.document_id }}</p>
              </div>
              <div>
                <span class="workflow-label">Chunk ID</span>
                <p>{{ source.chunk_id }}</p>
              </div>
              <div>
                <span class="workflow-label">匹配分数</span>
                <p>{{ source.score.toFixed(4) }}</p>
              </div>
            </div>
            <div class="source-detail-snippet">
              <span class="workflow-label">引用片段</span>
              <p>{{ source.content }}</p>
            </div>
          </div>
        </article>
      </div>
      <p
        v-if="!sourcesExpanded && latestSources.length > defaultVisibleSourceCount"
        class="source-collapsed-hint"
      >
        当前先展示最相关的 {{ defaultVisibleSourceCount }} 条来源，可展开查看更多候选片段。
      </p>
    </section>

    <div v-if="statusText || errorMessage" class="chat-status-bar" :class="{ error: Boolean(errorMessage) }">
      <span class="chat-status-label">{{ errorMessage || statusText }}</span>
      <span v-if="loading" class="typing-dots" aria-hidden="true">
        <i></i>
        <i></i>
        <i></i>
      </span>
    </div>
  </div>
</template>
