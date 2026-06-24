<script setup lang="ts">
defineProps<{
  tone?: "info" | "danger" | "success";
  message: string;
  dismissible?: boolean;
}>();

const emit = defineEmits<{
  dismiss: [];
}>();
</script>

<template>
  <div class="admin-notice" :class="tone || 'info'">
    <span>{{ message }}</span>
    <button
      v-if="dismissible"
      class="admin-notice-close"
      type="button"
      aria-label="关闭提示"
      @click="emit('dismiss')"
    >
      ×
    </button>
  </div>
</template>

<style scoped>
.admin-notice {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border: 1px solid #cdd9ea;
  border-radius: 8px;
  background: #f7fbff;
  color: #334155;
  font-size: 13px;
  line-height: 1.5;
}

.admin-notice.danger {
  border-color: rgba(220, 38, 38, 0.24);
  background: #fff5f5;
  color: #b91c1c;
}

.admin-notice.success {
  border-color: rgba(22, 163, 74, 0.24);
  background: #f2fbf5;
  color: #166534;
}

.admin-notice-close {
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: currentColor;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
}

.admin-notice-close:hover {
  background: rgba(15, 23, 42, 0.08);
}
</style>
