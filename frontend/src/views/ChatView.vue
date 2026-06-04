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
  latestSources,
  latestWorkflow,
  loadMessages,
  loadSessions,
  loading,
  messages,
  retryLastQuestion,
  selectSession,
  sessions,
  stopStreaming,
  statusText,
  streamMode
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
        当前聊天页支持同步问答与真实流式问答，回答会同时返回来源片段和工作流元数据，方便对齐 LangGraph
        的执行结果。
      </p>
    </div>

    <div class="chat-layout">
      <RetriFlowChatSessionList
        :active-session-id="activeSessionId"
        :loading="loading"
        :sessions="sessions"
        @create-session="createNewSession"
        @select-session="selectSession"
      />

      <div class="chat-pane">
        <div ref="transcriptContainer" class="transcript-shell">
          <RetriFlowChatTranscript
            :error-message="errorMessage"
            :has-messages="hasMessages"
            :latest-sources="latestSources"
            :latest-workflow="latestWorkflow"
            :loading="loading"
            :messages="messages"
            :status-text="statusText"
          />
        </div>

        <RetriFlowChatComposer
          v-model:draft="draft"
          v-model:stream-mode="streamMode"
          :can-stop="canStop"
          :can-retry="canRetry"
          :loading="loading"
          :prompts="starterPrompts"
          :status-text="statusText"
          @stop="stopStreaming"
          @retry="retryLastQuestion"
          @submit="submitPrompt()"
          @submit-prompt="submitPrompt"
        />
      </div>
    </div>
  </section>
</template>
