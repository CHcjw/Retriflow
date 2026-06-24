<script setup lang="ts">
import AdminModalShell from "../common/AdminModalShell.vue";

const content = defineModel<string>("content", { required: true });
const enabled = defineModel<boolean>("enabled", { required: true });

const emit = defineEmits<{
  close: [];
  save: [];
}>();
</script>

<template>
  <AdminModalShell aria-label="修改分块" description="更新分块内容与启用状态。" size="tall" title="修改分块" @close="emit('close')">
    <div class="modal-form single">
      <label class="modal-label">
        分块内容
        <textarea v-model="content" class="ui-input" rows="8" placeholder="请输入分块内容"></textarea>
      </label>
      <label class="modal-checkbox">
        <input v-model="enabled" type="checkbox" />
        启用分块
      </label>
    </div>
    <template #actions>
      <button class="ghost-btn" type="button" @click="emit('close')">取消</button>
      <button class="primary-btn" type="button" :disabled="!content.trim()" @click="emit('save')">保存</button>
    </template>
  </AdminModalShell>
</template>
