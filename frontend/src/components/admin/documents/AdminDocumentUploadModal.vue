<script setup lang="ts">
import type { IngestionPipelineItem } from "../../../services/pipelineApi";
import AdminModalShell from "../common/AdminModalShell.vue";
import AdminNotice from "../common/AdminNotice.vue";

type ChunkStrategyOption = {
  label: string;
  value: string;
};

defineProps<{
  chunkStrategyOptions: readonly ChunkStrategyOption[];
  editingDocumentId: number | null;
  error: string;
  hasSelectedFile: boolean;
  ingestionPipelines: IngestionPipelineItem[];
  selectedUploadFileLabel: string;
  uploadAccept: string;
  uploadAutoStrategyRecommendation: string;
  uploadChunkSummary: string;
  uploadLoading: boolean;
  uploadRecursiveSeparatorSummary: string;
  uploadShowChunkSizeControls: boolean;
  uploadShowRecursiveSeparatorControls: boolean;
  uploadShowSemanticNotice: boolean;
}>();

const editDocumentTitle = defineModel<string>("editDocumentTitle", { required: true });
const editDocumentEnabled = defineModel<boolean>("editDocumentEnabled", { required: true });
const uploadProcessMode = defineModel<string>("uploadProcessMode", { required: true });
const uploadPipelineId = defineModel<number | null>("uploadPipelineId", { required: true });
const uploadChunkStrategy = defineModel<string>("uploadChunkStrategy", { required: true });
const uploadChunkSize = defineModel<number>("uploadChunkSize", { required: true });
const uploadChunkOverlap = defineModel<number>("uploadChunkOverlap", { required: true });
const uploadStructureMaxChars = defineModel<number>("uploadStructureMaxChars", { required: true });
const uploadStructureMinChars = defineModel<number>("uploadStructureMinChars", { required: true });
const uploadRecursiveSeparatorsText = defineModel<string>("uploadRecursiveSeparatorsText", { required: true });

const emit = defineEmits<{
  clearError: [];
  close: [];
  fileSelected: [event: Event];
  save: [];
}>();
</script>

<template>
  <AdminModalShell
    aria-label="上传文档"
    :description="editingDocumentId ? '更新文档标题、启用状态和处理配置。' : '上传后解析源文件用于预览；切块参数会保存到文档，点击“切块”时执行。'"
    size="tall"
    :title="editingDocumentId ? '修改文档' : '上传文档'"
    @close="emit('close')"
  >
    <div class="modal-form single">
      <label v-if="editingDocumentId" class="modal-label">
        文档标题
        <input v-model="editDocumentTitle" class="ui-input modal-control" type="text" placeholder="请输入文档标题" />
      </label>
      <label class="modal-label">
        来源类型
        <select class="ui-input modal-control" disabled>
          <option>Local File</option>
        </select>
      </label>
      <label class="modal-label">
        本地文件
        <input :accept="uploadAccept" class="ui-input modal-file" type="file" :disabled="!!editingDocumentId" @change="emit('fileSelected', $event)" />
        <span>{{ selectedUploadFileLabel }}</span>
      </label>
      <div class="modal-config-section">
        <label class="modal-label">
          处理模式
          <select v-model="uploadProcessMode" class="ui-input modal-control">
            <option value="chunk_strategy">按切块策略处理</option>
            <option value="data_channel">按数据通道处理</option>
          </select>
        </label>
        <label v-if="uploadProcessMode === 'chunk_strategy'" class="modal-label">
          切块策略
          <select v-model="uploadChunkStrategy" class="ui-input modal-control">
            <option v-for="option in chunkStrategyOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <label v-else class="modal-label">
          数据通道
          <select v-model.number="uploadPipelineId" class="ui-input modal-control" :disabled="ingestionPipelines.length === 0">
            <option v-if="ingestionPipelines.length === 0" :value="null">暂无数据通道</option>
            <option v-for="pipeline in ingestionPipelines" :key="pipeline.id" :value="pipeline.id">
              {{ pipeline.name }}
            </option>
          </select>
        </label>
        <template v-if="uploadProcessMode === 'chunk_strategy'">
          <template v-if="uploadChunkStrategy === 'structure_aware'">
            <div class="modal-field-grid">
              <label class="modal-label">
                理想块大小
                <input v-model.number="uploadChunkSize" class="ui-input modal-control" min="1" type="number" />
              </label>
              <label class="modal-label">
                块上限
                <input v-model.number="uploadStructureMaxChars" class="ui-input modal-control" min="1" type="number" />
              </label>
            </div>
            <div class="modal-field-grid">
              <label class="modal-label">
                块下限
                <input v-model.number="uploadStructureMinChars" class="ui-input modal-control" min="1" type="number" />
              </label>
              <label class="modal-label">
                重叠大小
                <input v-model.number="uploadChunkOverlap" class="ui-input modal-control" min="0" type="number" />
              </label>
            </div>
          </template>
          <div v-else-if="uploadShowChunkSizeControls" class="modal-field-grid">
            <label class="modal-label">
              Chunk Size
              <input v-model.number="uploadChunkSize" class="ui-input modal-control" min="1" type="number" />
            </label>
            <label class="modal-label">
              Overlap
              <input v-model.number="uploadChunkOverlap" class="ui-input modal-control" min="0" type="number" />
            </label>
          </div>
          <label v-if="uploadShowRecursiveSeparatorControls" class="modal-label">
            递归分隔符
            <textarea v-model="uploadRecursiveSeparatorsText" class="ui-input" rows="4"></textarea>
          </label>
          <p class="modal-hint">{{ uploadChunkSummary }}</p>
          <p v-if="uploadAutoStrategyRecommendation" class="modal-hint">{{ uploadAutoStrategyRecommendation }}</p>
          <p v-if="uploadShowRecursiveSeparatorControls" class="modal-hint">{{ uploadRecursiveSeparatorSummary }}</p>
          <p v-if="uploadShowSemanticNotice" class="modal-hint">语义切块会保留策略配置，后端按当前可用能力执行。</p>
        </template>
      </div>
      <label v-if="editingDocumentId" class="modal-checkbox">
        <input v-model="editDocumentEnabled" type="checkbox" />
        启用文档
      </label>
      <p v-if="!editingDocumentId" class="modal-hint">
        上传只保存源文件并解析预览；分块、入库任务和向量化会在点击“切块”后执行。
      </p>
      <AdminNotice v-if="error" tone="danger" :message="error" dismissible @dismiss="emit('clearError')" />
    </div>
    <template #actions>
      <button class="ghost-btn" type="button" @click="emit('close')">取消</button>
      <button class="primary-btn" type="button" :disabled="uploadLoading || (!editingDocumentId && !hasSelectedFile) || (!!editingDocumentId && !editDocumentTitle.trim())" @click="emit('save')">
        {{ editingDocumentId ? "保存" : (uploadLoading ? "上传并解析中..." : "上传") }}
      </button>
    </template>
  </AdminModalShell>
</template>
