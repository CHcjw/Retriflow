import { shallowRef } from "vue";

import type { AdminKeywordMappingItem, AdminKeywordMappingUpsertRequest } from "../../../services/adminApi";

export function useAdminKeywordMappingForm() {
  const editingKeywordMappingId = shallowRef("");
  const newKeyword = shallowRef("");
  const newKeywordTarget = shallowRef("");
  const newKeywordMatchType = shallowRef("exact");
  const newKeywordPriority = shallowRef(0);
  const newKeywordEnabled = shallowRef("enabled");
  const newKeywordRemark = shallowRef("");

  function resetKeywordMappingForm() {
    editingKeywordMappingId.value = "";
    newKeyword.value = "";
    newKeywordTarget.value = "";
    newKeywordMatchType.value = "exact";
    newKeywordPriority.value = 0;
    newKeywordEnabled.value = "enabled";
    newKeywordRemark.value = "";
  }

  function fillKeywordMappingForm(mapping: AdminKeywordMappingItem) {
    editingKeywordMappingId.value = mapping.id;
    newKeyword.value = mapping.raw_keyword;
    newKeywordTarget.value = mapping.target_keyword;
    newKeywordMatchType.value = mapping.match_type;
    newKeywordPriority.value = mapping.priority;
    newKeywordEnabled.value = mapping.enabled ? "enabled" : "disabled";
    newKeywordRemark.value = mapping.remark;
  }

  function buildKeywordMappingPayload(knowledgeBaseId: string): AdminKeywordMappingUpsertRequest {
    const rawKeyword = newKeyword.value.trim();
    return {
      raw_keyword: rawKeyword,
      target_keyword: newKeywordTarget.value.trim() || rawKeyword,
      match_type: newKeywordMatchType.value,
      priority: Number(newKeywordPriority.value) || 0,
      enabled: newKeywordEnabled.value === "enabled",
      remark: newKeywordRemark.value.trim(),
      knowledge_base_id: knowledgeBaseId
    };
  }

  return {
    editingKeywordMappingId,
    newKeyword,
    newKeywordTarget,
    newKeywordMatchType,
    newKeywordPriority,
    newKeywordEnabled,
    newKeywordRemark,
    resetKeywordMappingForm,
    fillKeywordMappingForm,
    buildKeywordMappingPayload
  };
}
