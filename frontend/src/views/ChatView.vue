<script setup lang="ts">
import { nextTick, onMounted, shallowRef, useTemplateRef, watch } from "vue";

import RetriFlowChatComposer from "../components/chat/RetriFlowChatComposer.vue";
import RetriFlowChatSessionList from "../components/chat/RetriFlowChatSessionList.vue";
import RetriFlowChatTranscript from "../components/chat/RetriFlowChatTranscript.vue";
import { useRetriFlowChat } from "../composables/useRetriFlowChat";

const draft = shallowRef("");
const deepThinking = shallowRef(false);
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
  loadStarterPrompts,
  loadMessages,
  loadSessions,
  loading,
  messages,
  removeSession,
  renameSession,
  retryLastQuestion,
  selectSession,
  sessions,
  starterPrompts,
  statusText,
  stopStreaming,
  submitFeedback
} = useRetriFlowChat();

const submitPrompt = async (prompt?: string) => {
  const message = prompt ?? draft.value;
  if (!message.trim()) {
    return;
  }
  await ask(message, { deepThinking: deepThinking.value });
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
    await loadStarterPrompts();
    await loadMessages();
    await scrollToBottom();
  })();
});
</script>

<template>
  <div class="chat-layout">
    <RetriFlowChatSessionList
      :active-session-id="activeSessionId"
      :loading="loading"
      :sessions="sessions"
      @create-session="createNewSession"
      @delete-session="removeSession"
      @rename-session="renameSession"
      @select-session="selectSession"
    />

    <div class="chat-main-area">
      <div class="top-nav">
        <div class="nav-title">{{ sessions.find(s => s.id === activeSessionId)?.title || '新对话' }}</div>

      </div>

      <div class="scrollable-content" ref="transcriptContainer">
        <!-- If there are no messages, show the Welcome / Empty state (like Image 2) -->
        <div v-if="!hasMessages && !loading" class="empty-state">
          <div class="empty-hero">
            <span class="badge">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
              RetriFlow
            </span>
            <h1 class="hero-title">把问题变成<span class="highlight">清晰答案</span></h1>
            <p class="hero-subtitle">结构化提问、知识检索与深度思考，一次对话给出可执行方案</p>
          </div>
          
          <div class="composer-container center-composer">
            <RetriFlowChatComposer
              v-model:draft="draft"
              :can-stop="canStop"
              :can-retry="canRetry"
              :loading="loading"
              v-model:deep-thinking="deepThinking"
              :status-text="statusText"
              @retry="retryLastQuestion"
              @stop="stopStreaming"
              @submit="submitPrompt()"
            />
          </div>

          <div class="cards-section">
            <div class="section-title">
              <div class="line"></div>
              <span>试试这些开场</span>
              <div class="line"></div>
            </div>
            
            <div class="starter-cards">
              <div
                v-for="(prompt, index) in starterPrompts"
                :key="prompt"
                class="card"
                @click="submitPrompt(prompt)"
              >
                <div class="card-icon" :class="['system', 'realtime', 'business'][index % 3]">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
                </div>
                <div class="card-content">
                  <h4>{{ index === 0 ? "推荐问法" : "示例问题" }}</h4>
                  <p>{{ prompt }}</p>
                </div>
                <div class="card-hint">点击直接提问 ↗</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Transcript when there are messages (like Image 3) -->
        <div v-else class="transcript-wrapper">
          <RetriFlowChatTranscript
            :error-message="errorMessage"
            :has-messages="hasMessages"
            :latest-mcp-calls="latestMcpCalls"
            :latest-sources="latestSources"
            :latest-workflow="latestWorkflow"
            :loading="loading"
            :messages="messages"
            :status-text="statusText"
            @feedback="submitFeedback"
          />
        </div>
      </div>

      <!-- Sticky Composer for active chats -->
      <div v-if="hasMessages || loading" class="sticky-composer">
        <div class="composer-container">
          <RetriFlowChatComposer
            v-model:draft="draft"
            :can-stop="canStop"
            :can-retry="canRetry"
            :loading="loading"
            v-model:deep-thinking="deepThinking"
            :status-text="statusText"
            @retry="retryLastQuestion"
            @stop="stopStreaming"
            @submit="submitPrompt()"
          />
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.chat-layout {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: var(--surface);
}

.chat-main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: relative;
}

.top-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: var(--surface);
  z-index: 10;
}

.nav-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-main);
}

.star-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  background: white;
  transition: all 0.2s;
}

.star-btn:hover {
  background: var(--sidebar-bg);
  color: var(--text-main);
}

.star-btn svg {
  width: 14px;
  height: 14px;
}

.scrollable-content {
  flex: 1;
  overflow-y: auto;
  padding: 0 24px 40px;
  display: flex;
  flex-direction: column;
}

/* Empty State Styles */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}

.empty-hero {
  text-align: center;
  margin-bottom: 40px;
}

.empty-hero .badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 24px;
}

.empty-hero .badge svg {
  width: 14px;
  height: 14px;
}

.hero-title {
  font-size: 48px;
  font-weight: 700;
  color: var(--text-main);
  margin-bottom: 16px;
  letter-spacing: -0.02em;
}

.highlight {
  color: var(--primary);
}

.hero-subtitle {
  font-size: 16px;
  color: var(--text-muted);
}

.composer-container {
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
}

.center-composer {
  margin-bottom: 60px;
}

.cards-section {
  width: 100%;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.section-title .line {
  flex: 1;
  height: 1px;
  background: var(--border-light);
}

.section-title span {
  font-size: 13px;
  color: var(--text-light);
}

.starter-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.card {
  background: white;
  border: 1px solid var(--border-light);
  border-radius: 16px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
}

.card:hover {
  box-shadow: var(--shadow-md);
  border-color: rgba(90, 92, 250, 0.2);
  transform: translateY(-2px);
}

.card-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.card-icon svg {
  width: 16px;
  height: 16px;
}

.card-icon.system { background: #EBF1FB; color: var(--primary); }
.card-icon.realtime { background: #E6F7F2; color: var(--success); }
.card-icon.business { background: #F3F0FF; color: #8B5CF6; }

.card-content {
  flex: 1;
  margin-bottom: 16px;
}

.card-content h4 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 4px;
}

.card-content p {
  font-size: 13px;
  color: var(--text-muted);
}

.card-hint {
  font-size: 12px;
  color: var(--text-light);
}

/* Active Chat Styles */
.transcript-wrapper {
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
  padding-bottom: 20px;
}

.sticky-composer {
  padding: 20px 24px 32px;
  background: linear-gradient(to top, var(--surface) 80%, transparent);
  position: sticky;
  bottom: 0;
}
</style>
