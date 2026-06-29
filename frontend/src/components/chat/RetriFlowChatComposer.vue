<script setup lang="ts">
import { nextTick, useTemplateRef } from "vue";

const draft = defineModel<string>("draft", { required: true });
const deepThinking = defineModel<boolean>("deepThinking", { default: false });
const smartSearch = defineModel<boolean>("smartSearch", { default: false });
const textareaRef = useTemplateRef<HTMLTextAreaElement>("textareaRef");

defineProps<{
  canStop: boolean;
  canRetry: boolean;
  loading: boolean;
  statusText: string;
}>();

const emit = defineEmits<{
  stop: [];
  retry: [];
  submit: [];
}>();

const onKeydown = (event: KeyboardEvent) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    emit("submit");
  }
};

async function focusInput() {
  await nextTick();
  textareaRef.value?.focus();
}

function toggleDeepThinking() {
  deepThinking.value = !deepThinking.value;
}

function toggleSmartSearch() {
  smartSearch.value = !smartSearch.value;
}

defineExpose({
  focusInput,
  toggleDeepThinking,
  toggleSmartSearch
});
</script>

<template>
  <div class="composer-wrapper">
    <div class="composer-box">
      <textarea
        ref="textareaRef"
        v-model="draft"
        :disabled="loading"
        placeholder="输入你的问题..."
        rows="1"
        class="auto-resize-textarea"
        @keydown="onKeydown"
      ></textarea>

      <div class="composer-footer">
        <div class="left-actions">
          <button
            type="button"
            class="mode-btn"
            :class="{ active: deepThinking }"
            title="深度思考（Alt + D）"
            @click="toggleDeepThinking"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            深度思考
          </button>
          <button
            type="button"
            class="mode-btn"
            :class="{ active: smartSearch }"
            title="开启后优先使用联网搜索或天气 MCP（Alt + S）"
            @click="toggleSmartSearch"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M2 12h20" />
              <path d="M12 2a15.3 15.3 0 010 20" />
              <path d="M12 2a15.3 15.3 0 000 20" />
            </svg>
            智能搜索
          </button>
        </div>

        <div class="right-actions">
          <button
            v-if="canStop"
            type="button"
            class="action-btn stop-btn"
            title="停止生成"
            @click="emit('stop')"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          </button>

          <button
            v-if="canRetry"
            type="button"
            class="action-btn retry-btn"
            :disabled="loading"
            title="重试上一条"
            @click="emit('retry')"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>

          <button
            type="button"
            class="send-btn"
            :disabled="loading || !draft.trim()"
            title="发送"
            @click="emit('submit')"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <div class="composer-hints">
      Enter 发送，Shift + Enter 换行，/ 聚焦输入，Alt + S 智能搜索，Alt + D 深度思考
      <span v-if="statusText" class="status-text"> · {{ statusText }}</span>
    </div>
  </div>
</template>

<style scoped>
.composer-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.composer-box {
  width: 100%;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 252, 252, 0.96));
  border-radius: 20px;
  box-shadow:
    0 18px 46px rgba(23, 32, 51, 0.12),
    0 0 0 1px rgba(255, 255, 255, 0.8) inset;
  border: 1px solid rgba(15, 143, 130, 0.22);
  padding: 14px;
  display: flex;
  flex-direction: column;
  transition: all 0.2s;
  position: relative;
}

.composer-box:focus-within {
  border-color: rgba(15, 143, 130, 0.48);
  box-shadow:
    0 20px 52px rgba(15, 143, 130, 0.16),
    0 0 0 3px rgba(15, 143, 130, 0.1);
}

.auto-resize-textarea {
  width: 100%;
  min-height: 80px;
  max-height: 200px;
  resize: none;
  border: 1px solid rgba(130, 146, 164, 0.22);
  border-radius: 15px;
  font-size: 15px;
  color: var(--text-main);
  line-height: 1.65;
  background: rgba(255, 255, 255, 0.78);
  outline: none;
  padding: 12px 14px;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.9) inset;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.auto-resize-textarea:focus {
  border-color: rgba(15, 143, 130, 0.28);
  background: rgba(255, 255, 255, 0.94);
}

.auto-resize-textarea::placeholder {
  color: #8a98a8;
}

.composer-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}

.left-actions,
.right-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.left-actions {
  flex-wrap: wrap;
}

.mode-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid rgba(130, 146, 164, 0.18);
  background: rgba(255, 255, 255, 0.72);
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  transition: all 0.2s;
}

.mode-btn:hover,
.mode-btn.active {
  background: var(--primary-soft);
  border-color: rgba(15, 143, 130, 0.24);
  color: var(--primary);
}

.mode-btn svg {
  width: 14px;
  height: 14px;
}

.action-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  background: transparent;
  transition: all 0.2s;
}

.action-btn:hover {
  background: var(--sidebar-bg);
  color: var(--text-main);
}

.action-btn.stop-btn {
  color: var(--danger);
}

.action-btn.stop-btn:hover {
  background: rgba(239, 68, 68, 0.1);
}

.action-btn svg {
  width: 16px;
  height: 16px;
}

.send-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--sidebar-bg);
  color: var(--text-light);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.send-btn:not(:disabled) {
  background: var(--primary);
  color: white;
  box-shadow: 0 8px 20px rgba(15, 143, 130, 0.26);
}

.send-btn:not(:disabled):hover {
  transform: translateY(-1px);
  background: var(--primary-hover);
}

.send-btn svg {
  width: 16px;
  height: 16px;
}

.composer-hints {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-light);
  font-family: monospace;
}

.status-text {
  color: var(--primary);
}
</style>
