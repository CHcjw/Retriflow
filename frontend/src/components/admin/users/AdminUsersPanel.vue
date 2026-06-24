<script setup lang="ts">
import type { AdminUserItem } from "../../../services/adminApi";
import AdminTablePagination from "../common/AdminTablePagination.vue";

const search = defineModel<string>("search", { required: true });
const page = defineModel<number>("page", { required: true });

defineProps<{
  items: AdminUserItem[];
  pageSize: number;
  total: number;
}>();

const emit = defineEmits<{
  create: [];
  delete: [userId: string];
  edit: [userId: string];
  refresh: [];
  roleChange: [userId: string, role: string];
}>();

function formatDate(value: string) {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").slice(0, 19);
}
</script>

<template>
  <div class="page-head">
    <div>
      <h1>用户管理</h1>
      <p>管理后台账号与角色权限。</p>
    </div>
    <div class="page-actions">
      <input v-model="search" class="ui-input" type="text" placeholder="搜索用户名或角色" />
      <button class="ghost-btn" type="button" @click="emit('refresh')">刷新</button>
      <button class="primary-btn" type="button" @click="emit('create')">新增用户</button>
    </div>
  </div>

  <section class="table-card">
    <div class="table-scroll">
      <table class="data-table user-table">
        <thead>
          <tr>
            <th>用户</th>
            <th>角色</th>
            <th>创建时间</th>
            <th>更新时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in items" :key="user.id">
            <td><strong class="text-ellipsis" :title="user.username">{{ user.username }}</strong><p class="muted-line">{{ user.id }}</p></td>
            <td><span class="status-pill" :class="{ success: user.role === 'admin' }">{{ user.role }}</span></td>
            <td>{{ formatDate(user.created_at) }}</td>
            <td>{{ formatDate(user.created_at) }}</td>
            <td class="row-actions">
              <button class="ghost-btn compact" type="button" @click="emit('edit', user.id)">修改</button>
              <button class="ghost-btn compact" type="button" :disabled="user.role === 'admin'" @click="emit('roleChange', user.id, 'admin')">设置管理员</button>
              <button class="ghost-btn compact" type="button" :disabled="user.role === 'user'" @click="emit('roleChange', user.id, 'user')">设置普通用户</button>
              <button class="danger-btn compact" type="button" @click="emit('delete', user.id)">删除</button>
            </td>
          </tr>
          <tr v-if="total === 0">
            <td colspan="5" class="empty-cell">暂无匹配用户。</td>
          </tr>
        </tbody>
      </table>
    </div>
    <AdminTablePagination :page="page" :page-size="pageSize" :total="total" @change="page = $event" />
  </section>
</template>

<style scoped>
.text-ellipsis {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: top;
  white-space: nowrap;
}

.muted-line {
  margin: 4px 0 0;
  color: #8794aa;
  font-size: 12px;
}
</style>
