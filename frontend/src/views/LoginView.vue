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
const confirmPassword = shallowRef("");
const showPassword = shallowRef(false);
const localError = shallowRef("");
const localInfo = shallowRef("");

const redirectTarget = computed(() => {
  const rawRedirect = route.query.redirect;
  return typeof rawRedirect === "string" && rawRedirect.startsWith("/") ? rawRedirect : "/chat";
});

const title = computed(() => (mode.value === "login" ? "欢迎回来" : "创建账户"));
const subtitle = computed(() =>
  mode.value === "login" ? "登录后继续你的检索增强对话。" : "注册后即可使用 RetriFlow 对话与知识库能力。"
);

function switchMode(nextMode: "login" | "register") {
  mode.value = nextMode;
  localError.value = "";
  localInfo.value = "";
  confirmPassword.value = "";
}

async function submit() {
  localError.value = "";
  localInfo.value = "";
  const normalizedUsername = username.value.trim();

  if (!normalizedUsername || !password.value) {
    localError.value = "请输入用户名和密码。";
    return;
  }

  try {
    if (mode.value === "register") {
      if (password.value.length < 8) {
        localError.value = "密码至少需要 8 位。";
        return;
      }
      if (password.value !== confirmPassword.value) {
        localError.value = "两次输入的密码不一致。";
        return;
      }
      await authStore.register({
        username: normalizedUsername,
        password: password.value,
        role: "user"
      });
      localInfo.value = "注册成功，请继续登录。";
      switchMode("login");
      username.value = normalizedUsername;
      password.value = "";
      return;
    }

    await authStore.login(normalizedUsername, password.value);
    await router.replace(redirectTarget.value);
  } catch (submitError) {
    localError.value = submitError instanceof Error ? submitError.message : "提交失败";
  }
}
</script>

<template>
  <div class="login-container">
    <section class="login-card">
      <div class="brand-row">
        <div class="brand-mark">R</div>
        <div>
          <strong>RetriFlow</strong>
          <span>Agentic RAG Platform</span>
        </div>
      </div>

      <div class="login-header">
        <h1>{{ title }}</h1>
        <p>{{ subtitle }}</p>
      </div>

      <form class="login-form" @submit.prevent="submit">
        <label class="form-group">
          用户名
          <div class="input-wrapper">
            <span class="icon">⌾</span>
            <input v-model="username" autocomplete="username" placeholder="请输入用户名" required type="text" />
          </div>
        </label>

        <label class="form-group">
          密码
          <div class="input-wrapper">
            <span class="icon">⌘</span>
            <input
              v-model="password"
              :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
              :type="showPassword ? 'text' : 'password'"
              placeholder="请输入密码"
              required
            />
            <button class="icon-btn right-icon" type="button" @click="showPassword = !showPassword">
              {{ showPassword ? "隐藏" : "显示" }}
            </button>
          </div>
        </label>

        <label v-if="mode === 'register'" class="form-group">
          确认密码
          <div class="input-wrapper">
            <span class="icon">⌘</span>
            <input
              v-model="confirmPassword"
              autocomplete="new-password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="再次输入密码"
              required
            />
          </div>
        </label>

        <div class="form-options">
          <span>{{ mode === "login" ? "管理员可创建用户，也可以自助注册普通账户。" : "注册账户默认为普通用户角色。" }}</span>
        </div>

        <p v-if="localError || authStore.error" class="message danger">{{ localError || authStore.error }}</p>
        <p v-if="localInfo" class="message success">{{ localInfo }}</p>

        <button class="submit-btn" type="submit" :disabled="authStore.loading">
          {{ authStore.loading ? "处理中..." : mode === "login" ? "登录" : "注册" }}
        </button>
      </form>

      <div class="register-link">
        <template v-if="mode === 'login'">
          还没有账户？
          <button type="button" @click="switchMode('register')">注册</button>
        </template>
        <template v-else>
          已有账户？
          <button type="button" @click="switchMode('login')">去登录</button>
        </template>
      </div>
    </section>
  </div>
</template>

<style scoped>
.login-container {
  display: grid;
  flex: 1 1 auto;
  width: 100%;
  min-width: 0;
  min-height: 100vh;
  place-items: center;
  padding: 24px;
  background:
    radial-gradient(circle at 20% 20%, rgba(109, 61, 245, 0.16), transparent 32%),
    radial-gradient(circle at 80% 10%, rgba(14, 165, 233, 0.12), transparent 28%),
    linear-gradient(135deg, #f8fbff 0%, #eef4fb 100%);
}

.login-card {
  width: min(460px, 100%);
  border: 1px solid rgba(207, 216, 232, 0.82);
  border-radius: 28px;
  padding: 42px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 24px 70px rgba(31, 41, 55, 0.12);
  backdrop-filter: blur(18px);
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 34px;
}

.brand-mark {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border-radius: 16px;
  background: #6d3df5;
  color: white;
  font-weight: 800;
}

.brand-row strong,
.brand-row span {
  display: block;
}

.brand-row span,
.login-header p,
.form-options,
.register-link {
  color: #64748b;
}

.login-header {
  margin-bottom: 28px;
}

.login-header h1 {
  margin: 0 0 8px;
  color: #172033;
  font-size: 32px;
}

.login-header p {
  margin: 0;
}

.login-form,
.form-group {
  display: grid;
  gap: 16px;
}

.form-group {
  gap: 8px;
  color: #475569;
  font-weight: 700;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-wrapper input {
  width: 100%;
  height: 52px;
  border: 1px solid #dbe4f0;
  border-radius: 14px;
  padding: 0 74px 0 44px;
  color: #172033;
  font-size: 15px;
}

.input-wrapper input:focus {
  border-color: #6d3df5;
  box-shadow: 0 0 0 4px rgba(109, 61, 245, 0.1);
  outline: 0;
}

.icon {
  position: absolute;
  left: 15px;
  color: #94a3b8;
}

.icon-btn {
  border: 0;
  background: transparent;
  color: #6d3df5;
  cursor: pointer;
  font-weight: 700;
}

.right-icon {
  position: absolute;
  right: 14px;
}

.form-options {
  font-size: 13px;
}

.message {
  border-radius: 12px;
  margin: 0;
  padding: 12px 14px;
  font-size: 13px;
}

.message.danger {
  background: #fef2f2;
  color: #b91c1c;
}

.message.success {
  background: #f0fdf4;
  color: #15803d;
}

.submit-btn {
  height: 52px;
  border: 0;
  border-radius: 14px;
  background: #6d3df5;
  color: white;
  cursor: pointer;
  font-size: 16px;
  font-weight: 800;
}

.submit-btn:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.register-link {
  margin-top: 26px;
  text-align: center;
}

.register-link button {
  border: 0;
  background: transparent;
  color: #009688;
  cursor: pointer;
  font: inherit;
  font-weight: 800;
}
</style>
