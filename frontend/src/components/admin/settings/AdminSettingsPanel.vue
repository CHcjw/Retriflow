<script setup lang="ts">
defineProps<{
  cards: Array<{
    title: string;
    items: Array<{ label: string; value: string }>;
  }>;
}>();

const emit = defineEmits<{
  refresh: [];
}>();
</script>

<template>
  <div class="page-head">
    <div>
      <h1>系统配置</h1>
      <p>只读展示当前 application 配置，敏感密钥不会在后台展示。</p>
    </div>
    <button class="ghost-btn" type="button" @click="emit('refresh')">刷新</button>
  </div>

  <section class="settings-grid">
    <article v-for="card in cards" :key="card.title" class="task-card">
      <h2>{{ card.title }}</h2>
      <dl class="setting-list">
        <template v-for="item in card.items" :key="item.label">
          <dt>{{ item.label }}</dt>
          <dd>{{ item.value }}</dd>
        </template>
      </dl>
    </article>
  </section>
</template>

<style scoped>
.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.task-card {
  border: 1px solid #dbe4f0;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(34, 43, 63, 0.05);
  padding: 28px;
}

.task-card h2 {
  margin: 0;
  color: #172033;
  font-size: 18px;
}

.setting-list {
  display: grid;
  grid-template-columns: minmax(90px, auto) minmax(0, 1fr);
  gap: 10px 14px;
}

.setting-list dt {
  color: #64748b;
  font-weight: 700;
}

.setting-list dd {
  margin: 0;
  color: #172033;
  word-break: break-word;
}

@media (max-width: 1100px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
