import { onMounted, ref, shallowRef } from "vue";

import { fetchChatBootstrap, fetchKnowledgeBases, fetchMeta, fetchSessions } from "../services/api";

export function useRetriFlowOverview() {
  const loading = shallowRef(true);
  const error = shallowRef("");
  const meta = ref<Awaited<ReturnType<typeof fetchMeta>> | null>(null);
  const sessions = ref<Awaited<ReturnType<typeof fetchSessions>>["items"]>([]);
  const knowledgeBases = ref<Awaited<ReturnType<typeof fetchKnowledgeBases>>["items"]>([]);
  const bootstrap = ref<Awaited<ReturnType<typeof fetchChatBootstrap>> | null>(null);

  const load = async () => {
    loading.value = true;
    error.value = "";

    try {
      const [metaData, sessionData, knowledgeData, bootstrapData] = await Promise.all([
        fetchMeta(),
        fetchSessions(),
        fetchKnowledgeBases(),
        fetchChatBootstrap()
      ]);

      meta.value = metaData;
      sessions.value = sessionData.items;
      knowledgeBases.value = knowledgeData.items;
      bootstrap.value = bootstrapData;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "加载 RetriFlow 概览失败";
    } finally {
      loading.value = false;
    }
  };

  onMounted(() => {
    void load();
  });

  return {
    loading,
    error,
    meta,
    sessions,
    knowledgeBases,
    bootstrap,
    load
  };
}
