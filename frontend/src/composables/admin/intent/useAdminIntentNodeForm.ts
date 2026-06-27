import { shallowRef } from "vue";

import type { AdminIntentNodeItem, AdminIntentNodeUpsertRequest } from "../../../services/adminApi";

function parseLines(value: string): string[] {
  return value
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean);
}

export function useAdminIntentNodeForm() {
  const editingIntentNodeId = shallowRef("");
  const newIntentName = shallowRef("");
  const newIntentCode = shallowRef("");
  const newIntentLevel = shallowRef("CATEGORY");
  const newIntentType = shallowRef("KB");
  const newIntentParent = shallowRef("ROOT");
  const newIntentKnowledgeBaseId = shallowRef("");
  const newIntentMcpToolId = shallowRef("");
  const newIntentCollectionName = shallowRef("");
  const newIntentDescription = shallowRef("");
  const newIntentSampleQuestion = shallowRef("");
  const newIntentRuleSnippet = shallowRef("");
  const newIntentPrompt = shallowRef("");
  const newIntentParamPrompt = shallowRef("");
  const newIntentAdvanced = shallowRef("");
  const newIntentTopK = shallowRef<number | null>(5);
  const newIntentMinScore = shallowRef<number | null>(null);
  const newIntentSortOrder = shallowRef(0);
  const newIntentEnabled = shallowRef(true);

  function resetIntentNodeForm(options: { knowledgeBaseId: string; collectionName: string }) {
    editingIntentNodeId.value = "";
    newIntentName.value = "";
    newIntentCode.value = "";
    newIntentLevel.value = "CATEGORY";
    newIntentType.value = "KB";
    newIntentParent.value = "ROOT";
    newIntentKnowledgeBaseId.value = options.knowledgeBaseId;
    newIntentMcpToolId.value = "";
    newIntentCollectionName.value = options.collectionName;
    newIntentDescription.value = "";
    newIntentSampleQuestion.value = "";
    newIntentRuleSnippet.value = "";
    newIntentPrompt.value = "";
    newIntentParamPrompt.value = "";
    newIntentAdvanced.value = "";
    newIntentTopK.value = 5;
    newIntentMinScore.value = null;
    newIntentSortOrder.value = 0;
    newIntentEnabled.value = true;
  }

  function fillIntentNodeForm(node: AdminIntentNodeItem) {
    editingIntentNodeId.value = node.id;
    newIntentName.value = node.name;
    newIntentCode.value = node.code;
    newIntentLevel.value = node.level;
    newIntentType.value = node.node_type;
    newIntentParent.value = node.parent_id;
    newIntentKnowledgeBaseId.value = node.knowledge_base_id;
    newIntentMcpToolId.value = node.mcp_tool_id;
    newIntentCollectionName.value = node.collection_name;
    newIntentDescription.value = node.description;
    newIntentSampleQuestion.value = node.sample_questions.join("\n");
    newIntentRuleSnippet.value = node.rule_snippet;
    newIntentPrompt.value = node.prompt_template;
    newIntentParamPrompt.value = node.param_prompt_template;
    newIntentAdvanced.value = "";
    newIntentTopK.value = node.top_k ?? 5;
    newIntentMinScore.value = node.min_score ?? null;
    newIntentSortOrder.value = node.sort_order;
    newIntentEnabled.value = node.enabled;
  }

  function buildIntentNodePayload(): AdminIntentNodeUpsertRequest {
    const name = newIntentName.value.trim();
    return {
      name,
      code: newIntentCode.value.trim() || name.toLowerCase().replace(/\s+/gu, "_"),
      level: newIntentLevel.value,
      node_type: newIntentType.value,
      parent_id: newIntentParent.value || "ROOT",
      knowledge_base_id: newIntentKnowledgeBaseId.value,
      mcp_tool_id: newIntentMcpToolId.value.trim(),
      collection_name: newIntentCollectionName.value.trim(),
      description: newIntentDescription.value.trim(),
      sample_questions: parseLines(newIntentSampleQuestion.value),
      rule_snippet: newIntentRuleSnippet.value.trim(),
      prompt_template: newIntentPrompt.value.trim(),
      param_prompt_template: newIntentParamPrompt.value.trim(),
      top_k: newIntentTopK.value,
      min_score: newIntentMinScore.value,
      sort_order: Number(newIntentSortOrder.value) || 0,
      enabled: newIntentEnabled.value
    };
  }

  return {
    editingIntentNodeId,
    newIntentName,
    newIntentCode,
    newIntentLevel,
    newIntentType,
    newIntentParent,
    newIntentKnowledgeBaseId,
    newIntentMcpToolId,
    newIntentCollectionName,
    newIntentDescription,
    newIntentSampleQuestion,
    newIntentRuleSnippet,
    newIntentPrompt,
    newIntentParamPrompt,
    newIntentAdvanced,
    newIntentTopK,
    newIntentMinScore,
    newIntentSortOrder,
    newIntentEnabled,
    resetIntentNodeForm,
    fillIntentNodeForm,
    buildIntentNodePayload
  };
}
