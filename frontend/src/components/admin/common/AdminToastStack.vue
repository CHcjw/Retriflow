<script setup lang="ts">
import type { AdminToastItem } from "../../../composables/admin/common/useAdminToasts";

defineProps<{
  toasts: AdminToastItem[];
}>();

const emit = defineEmits<{
  dismiss: [id: number];
}>();
</script>

<template>
  <TransitionGroup class="admin-toast-stack" name="admin-toast" tag="div">
    <div v-for="toast in toasts" :key="toast.id" class="admin-toast" :class="toast.tone">
      <span>{{ toast.message }}</span>
      <button class="admin-toast-close" type="button" aria-label="关闭提示" @click="emit('dismiss', toast.id)">x</button>
    </div>
  </TransitionGroup>
</template>

<style scoped>
.admin-toast-stack {
  position: fixed;
  top: 18px;
  right: 18px;
  z-index: 80;
  display: flex;
  width: min(360px, calc(100vw - 28px));
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
}

.admin-toast {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  min-height: 42px;
  padding: 10px 12px;
  border: 1px solid #cdd9ea;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.16);
  color: #334155;
  font-size: 13px;
  line-height: 1.45;
  pointer-events: auto;
}

.admin-toast.success {
  border-color: rgba(22, 163, 74, 0.24);
  background: #f2fbf5;
  color: #166534;
}

.admin-toast.danger {
  border-color: rgba(220, 38, 38, 0.24);
  background: #fff5f5;
  color: #b91c1c;
}

.admin-toast-close {
  width: 22px;
  height: 22px;
  flex: 0 0 auto;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: currentColor;
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
}

.admin-toast-close:hover {
  background: rgba(15, 23, 42, 0.08);
}

.admin-toast-enter-active,
.admin-toast-leave-active {
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}

.admin-toast-enter-from,
.admin-toast-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
