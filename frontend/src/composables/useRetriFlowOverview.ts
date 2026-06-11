import { onMounted, ref, shallowRef, watch } from "vue";

import { fetchChatBootstrap, fetchKnowledgeBases, fetchMeta, fetchSessions } from "../services/api";
import { useAuthStore } from "../stores/auth";

export function useRetriFlowOverview() {
  const authStore = useAuthStore();
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
      meta.value = await fetchMeta();

      if (authStore.isAuthenticated) {
        const [sessionData, knowledgeData, bootstrapData] = await Promise.all([
          fetchSessions(),
          fetchKnowledgeBases(),
          fetchChatBootstrap()
        ]);
        sessions.value = sessionData.items;
        knowledgeBases.value = knowledgeData.items;
        bootstrap.value = bootstrapData;
      } else {
        sessions.value = [];
        knowledgeBases.value = [];
        bootstrap.value = null;
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : "加载 RetriFlow 概览失败";
    } finally {
      loading.value = false;
    }
  };

  watch(
    () => [authStore.bootstrapped, authStore.isAuthenticated],
    ([bootstrapped]) => {
      if (!bootstrapped) {
        return;
      }
      void load();
    },
    { immediate: false }
  );

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
