<script setup lang="ts">
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div>
        <p class="eyebrow">RetriFlow</p>
        <h1>Python Agentic RAG Platform</h1>
      </div>
      <nav class="nav-links">
        <RouterLink to="/">概览</RouterLink>
        <RouterLink to="/chat">聊天</RouterLink>
        <RouterLink to="/admin">后台</RouterLink>
      </nav>
    </header>

    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
