<script setup lang="ts">
import type { IngestionPipelineItem } from "../../../services/pipelineApi";
import AdminModalShell from "../common/AdminModalShell.vue";
import AdminNotice from "../common/AdminNotice.vue";

defineProps<{
  error: string;
  ingestionPipelines: IngestionPipelineItem[];
  metadataValid: boolean;
  selectedFile: File | null;
  uploadAccept: string;
  uploadLoading: boolean;
}>();

const pipelineId = defineModel<number | null>("pipelineId", { required: true });
const sourceType = defineModel<string>("sourceType", { required: true });
const metadataText = defineModel<string>("metadataText", { required: true });

const emit = defineEmits<{
  clearError: [];
  close: [];
  fileSelected: [event: Event];
  save: [];
}>();
</script>

<template>
  <AdminModalShell
    aria-label="新建通道任务"
    description="支持 Local File / URL / Feishu / S3 来源，Local File 会直接上传文件。"
    size="wide"
    title="新建通道任务"
    @close="emit('close')"
  >
    <div class="modal-form single">
      <label class="modal-label">
        流水线
        <select v-model="pipelineId" class="ui-input modal-control">
          <option v-for="pipeline in ingestionPipelines" :key="pipeline.id" :value="pipeline.id">
            {{ pipeline.name }}
          </option>
        </select>
      </label>
      <div class="modal-field-grid">
        <label class="modal-label">
          来源类型
          <select v-model="sourceType" class="ui-input modal-control">
            <option value="local_file">Local File</option>
            <option value="url" disabled>URL</option>
            <option value="feishu" disabled>Feishu</option>
            <option value="s3" disabled>S3</option>
          </select>
        </label>
        <label class="modal-label">
          本地文件
          <input :accept="uploadAccept" class="ui-input modal-file" type="file" @change="emit('fileSelected', $event)" />
          <span>{{ selectedFile?.name || "请选择文件" }}</span>
        </label>
      </div>
      <label class="modal-label">
        任务元数据（JSON，可选）
        <textarea v-model="metadataText" class="ui-input" rows="5" placeholder='{"source":"manual"}'></textarea>
      </label>
      <AdminNotice v-if="error" tone="danger" :message="error" dismissible @dismiss="emit('clearError')" />
    </div>
    <template #actions>
      <button class="ghost-btn" type="button" @click="emit('close')">取消</button>
      <button
        class="primary-btn"
        type="button"
        :disabled="uploadLoading || !pipelineId || !selectedFile || !metadataValid"
        @click="emit('save')"
      >
        {{ uploadLoading ? "创建中..." : "创建任务" }}
      </button>
    </template>
  </AdminModalShell>
</template>
