<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";
import { useRouter } from "vue-router";

import { getUnauthorizedEventName } from "./services/authApi";
import { useAuthStore } from "./stores/auth";

const authStore = useAuthStore();
const router = useRouter();

function handleUnauthorized() {
  authStore.logout();
  void router.push({ name: "login" });
}

function handleLogout() {
  authStore.logout();
  void router.push({ name: "login" });
}

onMounted(() => {
  void authStore.bootstrap();
  window.addEventListener(getUnauthorizedEventName(), handleUnauthorized);
});

onBeforeUnmount(() => {
  window.removeEventListener(getUnauthorizedEventName(), handleUnauthorized);
});
</script>

<template>
  <div class="app-shell">
    <RouterView />
  </div>
</template>
