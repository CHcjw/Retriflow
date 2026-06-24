<script setup lang="ts">
defineProps<{
  hint?: string;
  label: string;
  wide?: boolean;
}>();
</script>

<template>
  <label class="modal-label" :class="{ wide }">
    {{ label }}
    <slot />
    <span v-if="hint">{{ hint }}</span>
  </label>
</template>
