<script setup lang="ts">
import { useRetriFlowOverview } from "../composables/useRetriFlowOverview";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
const { loading, error, meta, sessions, knowledgeBases, bootstrap } = useRetriFlowOverview();
</script>

<template>
  <section class="hero-card">
    <p class="eyebrow">项目概览</p>
    <h2 v-if="meta">{{ meta.name }} / {{ meta.frontend_name }}</h2>
    <h2 v-else>RetriFlow 概览加载中</h2>
    <p class="hero-copy">
      当前项目已经从 Java SpringBoot + React 迁移到 Python + FastAPI + Vue，并逐步补齐
      LangChain、LangGraph、LangSmith 所需的 Agentic RAG 能力。首页默认展示公共信息，登录后再加载你的会话与知识库概览。
    </p>
    <p v-if="loading" class="status-copy">正在加载 RetriFlow 数据...</p>
    <p v-else-if="error" class="status-copy error-copy">{{ error }}</p>
    <p v-else-if="!authStore.isAuthenticated" class="status-copy">
      登录后可查看你的会话数、知识库数和聊天能力摘要。
    </p>
  </section>

  <section class="feature-grid">
    <article class="feature-card">
      <h3>主路由</h3>
      <p v-if="meta">{{ meta.primary_routes.join(" / ") }}</p>
      <p v-else>等待后端元信息</p>
    </article>

    <article class="feature-card">
      <h3>聊天能力</h3>
      <p v-if="bootstrap">{{ bootstrap.capabilities.join(" / ") }}</p>
      <p v-else>登录后显示聊天能力摘要</p>
    </article>

    <article class="feature-card">
      <h3>会话数</h3>
      <p>{{ sessions.length }}</p>
    </article>

    <article class="feature-card">
      <h3>知识库数</h3>
      <p>{{ knowledgeBases.length }}</p>
    </article>
  </section>
</template>
