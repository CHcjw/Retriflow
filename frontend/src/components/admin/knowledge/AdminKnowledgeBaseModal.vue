<script setup lang="ts">
import AdminModalShell from "../common/AdminModalShell.vue";

type EmbeddingModelOption = {
  label: string;
  value: string;
};

defineProps<{
  editingKnowledgeBaseId: string | null;
  knowledgeEmbeddingModelOptions: readonly EmbeddingModelOption[];
}>();

const name = defineModel<string>("name", { required: true });
const embeddingModel = defineModel<string>("embeddingModel", { required: true });
const collectionName = defineModel<string>("collectionName", { required: true });

const emit = defineEmits<{
  close: [];
  save: [];
}>();
</script>

<template>
  <AdminModalShell
    aria-label="知识库表单"
    :description="editingKnowledgeBaseId ? '更新知识库名称、模型和 collection 配置。' : '创建一个新的知识库，用于存储和检索文档。'"
    :title="editingKnowledgeBaseId ? '修改知识库' : '创建知识库'"
    @close="emit('close')"
  >
    <div class="modal-form single">
      <label class="modal-label">
        知识库名称
        <input v-model="name" class="ui-input modal-control" type="text" placeholder="例如：产品文档库" />
        <span>为知识库起一个易于识别的名称。</span>
      </label>
      <label class="modal-label">
        Embedding 模型
        <select v-model="embeddingModel" class="ui-input modal-control">
          <option v-for="model in knowledgeEmbeddingModelOptions" :key="model.value" :value="model.value">{{ model.label }}</option>
        </select>
        <span>用于该知识库后续切块入库时的向量化模型。</span>
      </label>
      <label class="modal-label">
        Collection 名称
        <input v-model="collectionName" class="ui-input modal-control" type="text" placeholder="例如：productdocs" />
        <span>后端会按此 collection 配置创建和展示知识库。</span>
      </label>
    </div>
    <template #actions>
      <button class="ghost-btn" type="button" @click="emit('close')">取消</button>
      <button class="primary-btn" type="button" :disabled="!name.trim()" @click="emit('save')">
        {{ editingKnowledgeBaseId ? "保存" : "创建" }}
      </button>
    </template>
  </AdminModalShell>
</template>