import { computed, ref } from "vue";
import { defineStore } from "pinia";


export const useAppStore = defineStore("app", () => {
  const productName = ref("RetriFlow");
  const capabilityCount = ref(5);

  const summary = computed(() => `${productName.value} 当前已接入 ${capabilityCount.value} 项核心能力`);

  return {
    productName,
    capabilityCount,
    summary
  };
});
