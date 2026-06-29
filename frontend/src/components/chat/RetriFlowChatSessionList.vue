<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, shallowRef, useTemplateRef } from "vue";
import { useRouter } from "vue-router";
import type { SessionItem } from "../../services/chatApi";
import { useAuthStore } from "../../stores/auth";

const props = defineProps<{
  activeSessionId: string;
  loading: boolean;
  sessions: SessionItem[];
}>();

const emit = defineEmits<{
  createSession: [];
  deleteSession: [sessionId: string];
  renameSession: [sessionId: string, title: string];
  selectSession: [sessionId: string];
}>();

const router = useRouter();
const authStore = useAuthStore();

const activeMenuSessionId = shallowRef("");
const editingSessionId = shallowRef("");
const editingSessionTitle = shallowRef("");
const searchQuery = shallowRef("");
const searchInputRef = useTemplateRef<HTMLInputElement>("searchInputRef");

const visibleSessions = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  if (!query) {
    return props.sessions;
  }
  return props.sessions.filter((session) => (session.title || "新对话").toLowerCase().includes(query));
});

function toggleMenu(sessionId: string) {
  if (activeMenuSessionId.value === sessionId) {
    activeMenuSessionId.value = "";
  } else {
    activeMenuSessionId.value = sessionId;
  }
}

function startRename(session: SessionItem) {
  editingSessionId.value = session.id;
  editingSessionTitle.value = session.title || "新对话";
  activeMenuSessionId.value = "";
  nextTick(() => {
    const el = document.getElementById(`rename-input-${session.id}`);
    if (el) {
      el.focus();
    }
  });
}

function saveRename(sessionId: string) {
  if (editingSessionTitle.value.trim()) {
    emit("renameSession", sessionId, editingSessionTitle.value.trim());
  }
  editingSessionId.value = "";
}

function cancelRename() {
  editingSessionId.value = "";
}

async function focusSearch() {
  await nextTick();
  searchInputRef.value?.focus();
  searchInputRef.value?.select();
}

function clearSearch() {
  searchQuery.value = "";
  searchInputRef.value?.blur();
}

function confirmDelete(sessionId: string) {
  emit("deleteSession", sessionId);
  activeMenuSessionId.value = "";
}

function handleWindowClick(e: MouseEvent) {
  const target = e.target as HTMLElement;
  if (!target.closest(".more-btn") && !target.closest(".session-dropdown-menu")) {
    activeMenuSessionId.value = "";
  }
}

onMounted(() => {
  window.addEventListener("click", handleWindowClick);
});

onUnmounted(() => {
  window.removeEventListener("click", handleWindowClick);
});

function handleLogout() {
  authStore.logout();
  router.push({ name: "login" });
}

defineExpose({
  clearSearch,
  focusSearch
});
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="app-brand">
        <div class="app-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M12 2a2 2 0 012 2v2h4a2 2 0 012 2v10a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2h4V4a2 2 0 012-2zm0 8a2 2 0 100 4 2 2 0 000-4z" /></svg>
        </div>
        <div class="brand-text">
          <h2>RetriFlow</h2>
          <span>Powered by AI</span>
        </div>
      </div>
    </div>

    <div class="sidebar-actions">
      <div class="quick-start-card">
        <div class="quick-start-header">
          <span>快速开始</span>
          <span class="badge">新内容</span>
        </div>
        <button class="new-chat-btn" @click="emit('createSession')" :disabled="loading">
          <span class="plus-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14" /></svg>
          </span>
          <div class="btn-text">
            <strong>新建对话</strong>
            <span>从空白开始</span>
          </div>
        </button>
        <button class="admin-panel-btn" @click="router.push('/admin')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><circle cx="12" cy="12" r="3" /></svg>
          管理后台
        </button>
      </div>
    </div>

    <div class="search-section">
      <div class="search-header">
        <span>搜索对话</span>
        <span class="shortcut">Ctrl / Cmd + K</span>
      </div>
      <div class="search-input">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
        <input
          ref="searchInputRef"
          v-model="searchQuery"
          type="text"
          placeholder="搜索对话..."
          @keydown.esc.prevent="clearSearch"
        />
      </div>
    </div>

    <div class="history-list">
      <div class="history-label">{{ searchQuery.trim() ? `搜索结果 · ${visibleSessions.length}` : "更早" }}</div>
      <ul>
        <li
          v-for="session in visibleSessions"
          :key="session.id"
          class="history-item"
          :class="{ active: session.id === activeSessionId }"
          @click="emit('selectSession', session.id)"
          style="position: relative;"
        >
          <template v-if="editingSessionId === session.id">
            <input
              :id="`rename-input-${session.id}`"
              type="text"
              class="rename-input"
              v-model="editingSessionTitle"
              @keydown.enter.stop="saveRename(session.id)"
              @keydown.esc.stop="cancelRename"
              @blur="saveRename(session.id)"
              @click.stop
            />
          </template>
          <template v-else>
            <span class="session-title">{{ session.title || '新对话' }}</span>
            <button class="more-btn" @click.stop="toggleMenu(session.id)">
               <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /><circle cx="5" cy="12" r="1" /></svg>
            </button>
            
            <div v-if="activeMenuSessionId === session.id" class="session-dropdown-menu" @click.stop>
              <button class="dropdown-item" @click.stop="startRename(session)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                <span>重命名</span>
              </button>
              <button class="dropdown-item delete" @click.stop="confirmDelete(session.id)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                <span>删除</span>
              </button>
            </div>
          </template>
        </li>
        <li v-if="visibleSessions.length === 0" class="empty-history-item">没有匹配的对话</li>
      </ul>
    </div>

    <div class="user-profile">
      <div class="avatar">
        <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=admin" alt="avatar" />
      </div>
      <span class="username">{{ authStore.currentUser?.username || 'admin' }}</span>
      <button class="logout-btn" @click="handleLogout">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /><circle cx="5" cy="12" r="1" /></svg>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 280px;
  height: 100vh;
  background: rgba(237, 243, 246, 0.92);
  border-right: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 24px 20px;
}

.app-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-icon {
  width: 36px;
  height: 36px;
  background: var(--primary);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.app-icon svg {
  width: 20px;
  height: 20px;
}

.brand-text h2 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main);
  margin: 0;
}

.brand-text span {
  font-size: 12px;
  color: var(--text-light);
}

.sidebar-actions {
  padding: 0 16px;
  margin-bottom: 24px;
}

.quick-start-card {
  background:
    linear-gradient(135deg, rgba(221, 244, 239, 0.96) 0%, rgba(231, 238, 249, 0.92) 100%);
  border-radius: 16px;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.5);
  box-shadow: inset 0 2px 4px rgba(255, 255, 255, 0.8), var(--shadow-sm);
}

.quick-start-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}

.badge {
  background: var(--primary);
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
}

.new-chat-btn {
  width: 100%;
  background: white;
  border-radius: 12px;
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: var(--shadow-sm);
  transition: transform 0.1s ease, box-shadow 0.2s ease;
  margin-bottom: 8px;
}

.new-chat-btn:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.plus-icon {
  width: 32px;
  height: 32px;
  background: var(--primary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.plus-icon svg {
  width: 18px;
  height: 18px;
}

.btn-text {
  text-align: left;
  display: flex;
  flex-direction: column;
}

.btn-text strong {
  font-size: 14px;
  color: var(--text-main);
}

.btn-text span {
  font-size: 12px;
  color: var(--text-light);
}

.admin-panel-btn {
  width: 100%;
  background: transparent;
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 8px;
  transition: background 0.2s;
}

.admin-panel-btn:hover {
  background: rgba(15, 143, 130, 0.08);
}

.admin-panel-btn svg {
  width: 16px;
  height: 16px;
}

.search-section {
  padding: 0 20px;
  margin-bottom: 24px;
}

.search-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.shortcut {
  color: var(--text-light);
}

.search-input {
  position: relative;
  display: flex;
  align-items: center;
}

.search-input svg {
  position: absolute;
  left: 12px;
  width: 16px;
  height: 16px;
  color: var(--text-light);
}

.search-input input {
  width: 100%;
  height: 36px;
  padding: 0 12px 0 36px;
  background: white;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  font-size: 13px;
  color: var(--text-main);
  transition: all 0.2s;
}

.search-input input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(15, 143, 130, 0.12);
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px;
}

.history-label {
  padding: 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-light);
  margin-bottom: 8px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-muted);
  font-size: 14px;
  transition: all 0.2s;
}

.history-item:hover {
  background: rgba(0, 0, 0, 0.03);
  color: var(--text-main);
}

.history-item.active {
  background: rgba(15, 143, 130, 0.12);
  color: var(--primary);
  font-weight: 500;
}

.empty-history-item {
  padding: 14px 12px;
  color: var(--text-light);
  font-size: 13px;
  text-align: center;
}

.session-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.more-btn {
  opacity: 0;
  color: var(--text-light);
  transition: opacity 0.2s;
  display: flex;
}

.history-item:hover .more-btn {
  opacity: 1;
}

.more-btn svg {
  width: 16px;
  height: 16px;
}

.user-profile {
  padding: 16px 20px;
  border-top: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  gap: 12px;
}

.avatar img {
  width: 32px;
  height: 32px;
  border-radius: 8px;
}

.username {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.logout-btn {
  color: var(--text-light);
}

.logout-btn svg {
  width: 16px;
  height: 16px;
}

.rename-input {
  width: 100%;
  padding: 4px 8px;
  border: 1.5px solid var(--primary);
  border-radius: 6px;
  font-size: 14px;
  color: var(--text-main);
  background: white;
  outline: none;
}

.session-dropdown-menu {
  position: absolute;
  right: 12px;
  top: 36px;
  background: white;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  box-shadow: var(--shadow-md);
  padding: 4px;
  z-index: 100;
  min-width: 110px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  font-size: 13px;
  color: var(--text-muted);
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  transition: all 0.15s;
  width: 100%;
  border: none;
  text-align: left;
}

.dropdown-item:hover {
  background: var(--sidebar-bg);
  color: var(--text-main);
}

.dropdown-item.delete {
  color: var(--danger, #ef4444);
}

.dropdown-item.delete:hover {
  background: #fef2f2;
  color: #ef4444;
}

.dropdown-item svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}
</style>
