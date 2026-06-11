<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";
import { useRouter } from "vue-router";

import { getUnauthorizedEventName } from "./services/api";
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
    <header class="app-header">
      <div>
        <p class="eyebrow">RetriFlow</p>
        <h1>Python Agentic RAG Platform</h1>
      </div>

      <div class="header-actions">
        <nav class="nav-links">
          <RouterLink to="/">概览</RouterLink>
          <RouterLink to="/chat">聊天</RouterLink>
          <RouterLink to="/admin">后台</RouterLink>
        </nav>

        <div class="user-chip">
          <template v-if="authStore.isAuthenticated && authStore.currentUser">
            <span>{{ authStore.currentUser.username }} · {{ authStore.currentUser.role }}</span>
            <button type="button" class="secondary-button compact-button" @click="handleLogout">退出</button>
          </template>
          <template v-else>
            <RouterLink class="secondary-button compact-button" to="/login">登录</RouterLink>
          </template>
        </div>
      </div>
    </header>

    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
