<script setup lang="ts">
import { computed, shallowRef } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const mode = shallowRef<"login" | "register">("login");
const username = shallowRef("admin");
const password = shallowRef("admin");
const registerRole = shallowRef("user");
const localError = shallowRef("");
const successMessage = shallowRef("");

const submitLabel = computed(() => (mode.value === "login" ? "登录 RetriFlow" : "创建账号"));
const redirectTarget = computed(() => {
  const rawRedirect = route.query.redirect;
  return typeof rawRedirect === "string" && rawRedirect.startsWith("/") ? rawRedirect : "/chat";
});

async function submit() {
  localError.value = "";
  successMessage.value = "";

  try {
    if (mode.value === "register") {
      await authStore.register({
        username: username.value.trim(),
        password: password.value,
        role: registerRole.value
      });
      successMessage.value = "注册成功，请继续登录。";
      mode.value = "login";
      return;
    }

    await authStore.login(username.value.trim(), password.value);
    await router.replace(redirectTarget.value);
  } catch (submitError) {
    localError.value = submitError instanceof Error ? submitError.message : "提交失败";
  }
}

function switchMode(nextMode: "login" | "register") {
  mode.value = nextMode;
  localError.value = "";
  successMessage.value = "";
}
</script>

<template>
  <section class="page-panel auth-panel">
    <div class="panel-header">
      <p class="eyebrow">Account</p>
      <h2>{{ mode === "login" ? "登录 RetriFlow" : "注册 RetriFlow 账号" }}</h2>
    </div>

    <p class="hero-copy">
      登录后可使用会话、知识库后台和受保护的 RAG 能力。当前默认已经预置测试账号 `admin / admin`。
    </p>

    <div class="auth-tab-row">
      <button
        type="button"
        class="secondary-button"
        :class="{ 'is-active': mode === 'login' }"
        @click="switchMode('login')"
      >
        登录
      </button>
      <button
        type="button"
        class="secondary-button"
        :class="{ 'is-active': mode === 'register' }"
        @click="switchMode('register')"
      >
        注册
      </button>
    </div>

    <form class="document-form auth-form" @submit.prevent="submit">
      <label class="field-stack">
        <span>用户名</span>
        <input v-model="username" type="text" autocomplete="username" placeholder="请输入用户名" />
      </label>

      <label class="field-stack">
        <span>密码</span>
        <input v-model="password" type="password" autocomplete="current-password" placeholder="请输入密码" />
      </label>

      <label v-if="mode === 'register'" class="field-stack">
        <span>角色</span>
        <select v-model="registerRole">
          <option value="user">user</option>
          <option value="admin">admin</option>
        </select>
      </label>

      <p v-if="successMessage" class="status-copy">{{ successMessage }}</p>
      <p v-if="localError || authStore.error" class="status-copy error-copy">{{ localError || authStore.error }}</p>

      <button type="submit" :disabled="authStore.loading || !username.trim() || !password.trim()">
        {{ authStore.loading ? "提交中..." : submitLabel }}
      </button>
    </form>
  </section>
</template>
