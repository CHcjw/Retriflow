<script setup lang="ts">
import { useRetriFlowOverview } from "../composables/useRetriFlowOverview";

const { loading, error, meta, sessions, knowledgeBases, bootstrap } = useRetriFlowOverview();
</script>

<template>
  <section class="hero-card">
    <p class="eyebrow">项目概览</p>
    <h2 v-if="meta">{{ meta.name }} / {{ meta.frontend_name }}</h2>
    <h2 v-else>RetriFlow 概览加载中</h2>
    <p class="hero-copy">
      当前首页已经接入后端 meta、会话、知识库和聊天能力概览接口。项目骨架已经从 Java SpringBoot + React
      迁移到了 Python + FastAPI + Vue，并保持 LangGraph-ready 的 RAG 工作流结构。
    </p>
    <p v-if="loading" class="status-copy">正在加载 RetriFlow 数据...</p>
    <p v-else-if="error" class="status-copy error-copy">{{ error }}</p>
  </section>

  <section class="feature-grid">
    <article class="feature-card">
      <h3>主路由</h3>
      <p v-if="meta">{{ meta.primary_routes.join(" / ") }}</p>
    </article>

    <article class="feature-card">
      <h3>聊天能力</h3>
      <p v-if="bootstrap">{{ bootstrap.capabilities.join("、") }}</p>
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
