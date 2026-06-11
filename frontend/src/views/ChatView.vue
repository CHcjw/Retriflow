<script setup lang="ts">
import { nextTick, onMounted, shallowRef, useTemplateRef, watch } from "vue";

import RetriFlowChatComposer from "../components/chat/RetriFlowChatComposer.vue";
import RetriFlowChatSessionList from "../components/chat/RetriFlowChatSessionList.vue";
import RetriFlowChatTranscript from "../components/chat/RetriFlowChatTranscript.vue";
import { useRetriFlowChat } from "../composables/useRetriFlowChat";

const starterPrompts = [
  "RetriFlow 一期应该先做什么？",
  "知识库入库链路需要哪些节点？",
  "怎么把 ragent 的 trace 迁移到 LangSmith？"
];

const draft = shallowRef("");
const transcriptContainer = useTemplateRef<HTMLDivElement>("transcriptContainer");
const {
  activeSessionId,
  ask,
  canStop,
  canRetry,
  createNewSession,
  errorMessage,
  hasMessages,
  latestMcpCalls,
  latestSources,
  latestWorkflow,
  loadMessages,
  loadSessions,
  loading,
  messages,
  removeSession,
  retryLastQuestion,
  selectSession,
  sessions,
  statusText,
  stopStreaming
} = useRetriFlowChat();

const submitPrompt = async (prompt?: string) => {
  const message = prompt ?? draft.value;
  if (!message.trim()) {
    return;
  }
  await ask(message);
  draft.value = "";
};

const scrollToBottom = async () => {
  await nextTick();
  const container = transcriptContainer.value;
  if (!container) {
    return;
  }
  container.scrollTop = container.scrollHeight;
};

watch(
  () => [
    messages.value.length,
    messages.value[messages.value.length - 1]?.content ?? "",
    latestSources.value.length,
    latestWorkflow.value?.retrieval_count ?? 0,
    latestMcpCalls.value.length,
    loading.value
  ],
  () => {
    void scrollToBottom();
  }
);

onMounted(() => {
  void (async () => {
    await loadSessions();
    await loadMessages();
    await scrollToBottom();
  })();
});
</script>

<template>
  <section class="page-panel">
    <div class="panel-header">
      <p class="eyebrow">聊天工作台</p>
      <h2>会话与检索问答控制台</h2>
    </div>

    <div class="toolbar-row">
      <p class="hero-copy">
        当前聊天页默认使用流式回答，并同步展示参考来源与工具调用结果，让对话体验更接近真实产品，而不是调试面板。
      </p>
    </div>

    <div class="chat-layout">
      <RetriFlowChatSessionList
        :active-session-id="activeSessionId"
        :loading="loading"
        :sessions="sessions"
        @create-session="createNewSession"
        @delete-session="removeSession"
        @select-session="selectSession"
      />

      <div class="chat-pane">
        <div ref="transcriptContainer" class="transcript-shell">
          <RetriFlowChatTranscript
            :error-message="errorMessage"
            :has-messages="hasMessages"
            :latest-mcp-calls="latestMcpCalls"
            :latest-sources="latestSources"
            :latest-workflow="latestWorkflow"
            :loading="loading"
            :messages="messages"
            :status-text="statusText"
          />
        </div>

        <RetriFlowChatComposer
          v-model:draft="draft"
          :can-stop="canStop"
          :can-retry="canRetry"
          :loading="loading"
          :prompts="starterPrompts"
          :status-text="statusText"
          @retry="retryLastQuestion"
          @stop="stopStreaming"
          @submit="submitPrompt()"
          @submit-prompt="submitPrompt"
        />
      </div>
    </div>
  </section>
</template>
