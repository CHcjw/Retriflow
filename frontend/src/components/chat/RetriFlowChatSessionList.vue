<script setup lang="ts">
import type { SessionItem } from "../../services/api";

defineProps<{
  activeSessionId: string;
  loading: boolean;
  sessions: SessionItem[];
}>();

const emit = defineEmits<{
  createSession: [];
  deleteSession: [sessionId: string];
  selectSession: [sessionId: string];
}>();
</script>

<template>
  <aside class="session-pane">
    <div class="pane-title-row">
      <h3>会话列表</h3>
      <button type="button" class="secondary-button" :disabled="loading" @click="emit('createSession')">
        新建
      </button>
    </div>

    <p v-if="sessions.length === 0" class="status-copy">还没有会话，先创建一个开始吧。</p>

    <ul v-else>
      <li
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{ active: session.id === activeSessionId }"
        @click="emit('selectSession', session.id)"
      >
        <strong>{{ session.title }}</strong>
        <div class="pane-title-row">
          <span>{{ session.message_count }} 条消息</span>
          <button
            type="button"
            class="secondary-button compact-button danger-button"
            :disabled="loading"
            @click.stop="emit('deleteSession', session.id)"
          >
            删除
          </button>
        </div>
      </li>
    </ul>
  </aside>
</template>
