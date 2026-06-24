<script setup lang="ts">
defineProps<{
  ariaLabel: string;
  description?: string;
  size?: "default" | "tall" | "wide";
  title: string;
}>();

const emit = defineEmits<{
  close: [];
}>();
</script>

<template>
  <section
    class="admin-modal"
    :class="{
      'admin-modal-tall': size === 'tall',
      'admin-modal-wide': size === 'wide'
    }"
    :aria-label="ariaLabel"
  >
    <header class="modal-head">
      <div>
        <h2>{{ title }}</h2>
        <p v-if="description">{{ description }}</p>
      </div>
      <button class="modal-close" type="button" aria-label="关闭" @click="emit('close')">×</button>
    </header>

    <slot />

    <footer v-if="$slots.actions" class="modal-actions">
      <slot name="actions" />
    </footer>
  </section>
</template>
