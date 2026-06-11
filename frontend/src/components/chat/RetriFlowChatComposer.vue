<script setup lang="ts">
const draft = defineModel<string>("draft", { required: true });

defineProps<{
  canStop: boolean;
  canRetry: boolean;
  loading: boolean;
  prompts: string[];
  statusText: string;
}>();

const emit = defineEmits<{
  stop: [];
  retry: [];
  submit: [];
  submitPrompt: [prompt: string];
}>();

const onKeydown = (event: KeyboardEvent) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    emit("submit");
  }
};
</script>

<template>
  <div class="prompt-list">
    <button
      v-for="prompt in prompts"
      :key="prompt"
      type="button"
      class="prompt-pill"
      :disabled="loading"
      @click="emit('submitPrompt', prompt)"
    >
      {{ prompt }}
    </button>
  </div>

  <div class="composer">
    <textarea
      v-model="draft"
      rows="4"
      :disabled="loading"
      placeholder="输入你的问题。当前页面默认使用流式回答。"
      @keydown="onKeydown"
    ></textarea>
    <div class="composer-actions">
      <div class="composer-meta">
        <span class="status-copy">{{ statusText || "按 Ctrl/Cmd + Enter 可快速发送" }}</span>
      </div>
      <div class="inline-actions">
        <button
          v-if="canStop"
          type="button"
          class="secondary-button danger-button"
          :disabled="!canStop"
          @click="emit('stop')"
        >
          停止生成
        </button>
        <button v-if="canRetry" type="button" class="secondary-button" :disabled="loading" @click="emit('retry')">
          重试上一条
        </button>
        <button type="button" :disabled="loading || !draft.trim()" @click="emit('submit')">
          {{ loading ? "发送中..." : "发送" }}
        </button>
      </div>
    </div>
  </div>
</template>
