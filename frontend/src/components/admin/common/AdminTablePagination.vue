<script setup lang="ts">
const props = defineProps<{
  page: number;
  pageSize?: number;
  total: number;
}>();

const emit = defineEmits<{
  change: [page: number];
}>();

const pageSize = props.pageSize ?? 10;
const totalPages = () => Math.max(1, Math.ceil(props.total / pageSize));
const currentPage = () => Math.min(Math.max(1, props.page), totalPages());

function goPrevious() {
  emit("change", Math.max(1, currentPage() - 1));
}

function goNext() {
  emit("change", Math.min(totalPages(), currentPage() + 1));
}
</script>

<template>
  <div class="table-pagination">
    <span>第 {{ currentPage() }} / {{ totalPages() }} 页，共 {{ total }} 条</span>
    <div>
      <button class="ghost-btn compact" type="button" :disabled="currentPage() <= 1" @click="goPrevious">上一页</button>
      <button class="ghost-btn compact" type="button" :disabled="currentPage() >= totalPages()" @click="goNext">下一页</button>
    </div>
  </div>
</template>
