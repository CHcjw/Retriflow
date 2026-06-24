import { computed, ref } from "vue";
import { defineStore } from "pinia";

import {
  fetchCurrentUser,
  loginWithPassword,
  registerUser,
  setAccessToken,
  type AuthLoginResponse,
  type AuthRegisterRequest,
  type AuthUser
} from "../services/authApi";

const ACCESS_TOKEN_STORAGE_KEY = "retriflow.access_token";

function readStoredAccessToken(): string {
  if (typeof window === "undefined") {
    return "";
  }

  return window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY) ?? "";
}

function persistAccessToken(token: string) {
  if (typeof window === "undefined") {
    return;
  }

  if (token) {
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
    return;
  }

  window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
}

export const useAuthStore = defineStore("auth", () => {
  const accessToken = ref(readStoredAccessToken());
  const currentUser = ref<AuthUser | null>(null);
  const bootstrapped = ref(false);
  const loading = ref(false);
  const error = ref("");

  const isAuthenticated = computed(() => Boolean(accessToken.value && currentUser.value));
  const isAdmin = computed(() => currentUser.value?.role === "admin");

  function applyToken(token: string) {
    accessToken.value = token;
    persistAccessToken(token);
    setAccessToken(token);
  }

  async function bootstrap() {
    if (bootstrapped.value) {
      return;
    }

    bootstrapped.value = true;
    const token = readStoredAccessToken();
    applyToken(token);

    if (!token) {
      currentUser.value = null;
      return;
    }

    loading.value = true;
    error.value = "";

    try {
      currentUser.value = await fetchCurrentUser();
    } catch (bootstrapError) {
      currentUser.value = null;
      applyToken("");
      error.value = bootstrapError instanceof Error ? bootstrapError.message : "登录态恢复失败";
    } finally {
      loading.value = false;
    }
  }

  async function login(username: string, password: string): Promise<AuthLoginResponse> {
    loading.value = true;
    error.value = "";

    try {
      const response = await loginWithPassword({ username, password });
      applyToken(response.access_token);
      currentUser.value = response.user;
      return response;
    } catch (loginError) {
      error.value = loginError instanceof Error ? loginError.message : "登录失败";
      throw loginError;
    } finally {
      loading.value = false;
    }
  }

  async function register(payload: AuthRegisterRequest): Promise<AuthUser> {
    loading.value = true;
    error.value = "";

    try {
      return await registerUser(payload);
    } catch (registerError) {
      error.value = registerError instanceof Error ? registerError.message : "注册失败";
      throw registerError;
    } finally {
      loading.value = false;
    }
  }

  function logout() {
    currentUser.value = null;
    error.value = "";
    applyToken("");
  }

  return {
    accessToken,
    bootstrapped,
    currentUser,
    error,
    isAdmin,
    isAuthenticated,
    loading,
    bootstrap,
    login,
    logout,
    register
  };
});
