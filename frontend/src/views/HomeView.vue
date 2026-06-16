<script setup lang="ts">
import { useRetriFlowOverview } from "../composables/useRetriFlowOverview";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
const { loading, error, meta, sessions, knowledgeBases, bootstrap } = useRetriFlowOverview();
</script>

<template>
  <div class="home-container">
    <div class="home-content">
      <section class="hero-card">
        <p class="eyebrow">项目概览</p>
        <h2 class="hero-title" v-if="meta">{{ meta.name }} / {{ meta.frontend_name }}</h2>
        <h2 class="hero-title" v-else>RetriFlow 概览加载中</h2>
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
          <p class="feature-number">{{ sessions.length }}</p>
        </article>

        <article class="feature-card">
          <h3>知识库数</h3>
          <p class="feature-number">{{ knowledgeBases.length }}</p>
        </article>
      </section>
      
      <div class="home-actions">
         <router-link to="/chat" class="btn primary-btn">进入对话</router-link>
         <router-link to="/admin" class="btn outline-btn">进入后台</router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-container {
  width: 100vw;
  min-height: 100vh;
  background: var(--surface);
  display: flex;
  justify-content: center;
  padding: 64px 24px;
}

.home-content {
  max-width: 900px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.hero-card {
  background: linear-gradient(135deg, var(--bg-gradient-start), var(--bg-gradient-end));
  border-radius: 24px;
  padding: 48px;
  box-shadow: var(--shadow-md);
}

.eyebrow {
  color: var(--primary);
  font-size: 14px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 12px;
}

.hero-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-main);
  margin-bottom: 20px;
}

.hero-copy {
  font-size: 16px;
  color: var(--text-muted);
  line-height: 1.6;
  max-width: 600px;
}

.status-copy {
  margin-top: 16px;
  font-size: 14px;
  color: var(--text-light);
}

.error-copy {
  color: var(--danger);
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.feature-card {
  background: white;
  border: 1px solid var(--border-light);
  border-radius: 16px;
  padding: 24px;
  box-shadow: var(--shadow-sm);
  transition: transform 0.2s;
}

.feature-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.feature-card h3 {
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.feature-card p {
  font-size: 15px;
  color: var(--text-main);
  font-weight: 500;
}

.feature-number {
  font-size: 32px !important;
  font-weight: 700 !important;
  color: var(--primary) !important;
}

.home-actions {
   display: flex;
   gap: 16px;
   margin-top: 16px;
}

.btn {
   padding: 12px 24px;
   border-radius: 999px;
   font-size: 15px;
   font-weight: 600;
   transition: all 0.2s;
   text-align: center;
}

.primary-btn {
   background: var(--primary);
   color: white;
}
.primary-btn:hover {
   background: var(--primary-hover);
   transform: translateY(-1px);
}

.outline-btn {
   background: white;
   color: var(--text-main);
   border: 1px solid var(--border-light);
}
.outline-btn:hover {
   background: #F8FAFC;
}
</style>
