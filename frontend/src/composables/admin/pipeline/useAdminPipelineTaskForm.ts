import { shallowRef, type Ref } from "vue";

import type { IngestionPipelineItem } from "../../../services/pipelineApi";

const DEFAULT_METADATA = '{"source":"manual"}';

export function useAdminPipelineTaskForm(options: {
  ingestionPipelines: Ref<IngestionPipelineItem[]>;
}) {
  const newPipelineTaskPipelineId = shallowRef<number | null>(null);
  const newPipelineTaskSourceType = shallowRef("local_file");
  const newPipelineTaskFile = shallowRef<File | null>(null);
  const newPipelineTaskMetadataText = shallowRef(DEFAULT_METADATA);

  function resetPipelineTaskForm() {
    newPipelineTaskPipelineId.value = options.ingestionPipelines.value[0]?.id ?? null;
    newPipelineTaskSourceType.value = "local_file";
    newPipelineTaskFile.value = null;
    newPipelineTaskMetadataText.value = DEFAULT_METADATA;
  }

  function onPipelineTaskFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    newPipelineTaskFile.value = input.files?.[0] ?? null;
  }

  function pipelineTaskMetadataValid() {
    if (!newPipelineTaskMetadataText.value.trim()) {
      return true;
    }
    try {
      JSON.parse(newPipelineTaskMetadataText.value);
      return true;
    } catch {
      return false;
    }
  }

  function clearPipelineTaskFile() {
    newPipelineTaskFile.value = null;
  }

  return {
    newPipelineTaskPipelineId,
    newPipelineTaskSourceType,
    newPipelineTaskFile,
    newPipelineTaskMetadataText,
    clearPipelineTaskFile,
    onPipelineTaskFileSelected,
    pipelineTaskMetadataValid,
    resetPipelineTaskForm
  };
}
