<script setup lang="ts">
import { computed, shallowRef } from "vue";

import type { ChatMessage } from "../../composables/useRetriFlowChat";
import type { ChatSourceItem, ChatWorkflow } from "../../services/api";

const props = defineProps<{
  errorMessage: string;
  hasMessages: boolean;
  latestSources: ChatSourceItem[];
  latestWorkflow: ChatWorkflow | null;
  loading: boolean;
  messages: ChatMessage[];
  statusText: string;
}>();

const sourcesExpanded = shallowRef(true);
const sourceToggleLabel = computed(() => (sourcesExpanded.value ? "折叠来源" : "展开来源"));
const visibleSources = computed(() => (sourcesExpanded.value ? props.latestSources : []));

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function markdownToHtml(value: string): string {
  const escaped = escapeHtml(value);
  return escaped
    .replace(/^##\s+(.+)$/gm, "<h4>$1</h4>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/\[(\d+)\]/g, '<span class="citation">[$1]</span>')
    .replace(/\n/g, "<br>");
}
</script>

<template>
  <div class="chat-transcript">
    <div v-if="!hasMessages" class="empty-state-card">
      <p class="status-copy">聊天记录会显示在这里。</p>
    </div>

    <div
      v-for="message in messages"
      :key="message.id"
      class="message-card"
      :class="[message.role, `is-${message.state}`]"
    >
      <div class="pane-title-row">
        <strong>{{ message.role === "assistant" ? "RetriFlow" : "用户" }}</strong>
        <span v-if="message.state === 'streaming'" class="message-state-pill">生成中</span>
        <span v-else-if="message.state === 'stopped'" class="message-state-pill muted">已停止</span>
        <span v-else-if="message.state === 'error'" class="message-state-pill error">失败</span>
      </div>
      <div class="message-body" v-html="markdownToHtml(message.content || '正在等待模型返回...')"></div>
    </div>

    <section v-if="latestWorkflow" class="sources-panel">
      <div class="pane-title-row">
        <h3>本次工作流</h3>
        <span class="status-badge">{{ latestWorkflow.name }}</span>
      </div>
      <p class="status-copy">
        adapter: {{ latestWorkflow.adapter }}
        channels: {{ latestWorkflow.retrieval_channels.join(", ") }}
        sources: {{ latestWorkflow.retrieval_count }}
      </p>
    </section>

    <section v-if="latestSources.length > 0" class="sources-panel">
      <div class="pane-title-row">
        <h3>本次命中的来源</h3>
        <div class="inline-actions">
          <span class="status-copy">{{ latestSources.length }} 条</span>
          <button type="button" class="secondary-button compact-button" @click="sourcesExpanded = !sourcesExpanded">
            {{ sourceToggleLabel }}
          </button>
        </div>
      </div>
      <article v-for="source in visibleSources" :key="source.chunk_id" class="message-card source-card">
        <div class="pane-title-row">
          <strong>{{ source.document_title }}</strong>
          <span class="status-badge">score {{ source.score.toFixed(2) }}</span>
        </div>
        <p>{{ source.content }}</p>
      </article>
    </section>

    <div v-if="statusText || errorMessage" class="chat-status-bar" :class="{ error: Boolean(errorMessage) }">
      <span>{{ errorMessage || statusText }}</span>
      <span v-if="loading" class="typing-dots" aria-hidden="true">
        <i></i>
        <i></i>
        <i></i>
      </span>
    </div>
  </div>
</template>
