<script setup lang="ts">
import AdminModalShell from "../common/AdminModalShell.vue";
import AdminFormField from "../common/AdminFormField.vue";

defineProps<{
  editingUserId: string | null;
}>();

const username = defineModel<string>("username", { required: true });
const password = defineModel<string>("password", { required: true });
const role = defineModel<string>("role", { required: true });
const avatarUrl = defineModel<string>("avatarUrl", { required: true });

const emit = defineEmits<{
  close: [];
  save: [];
}>();
</script>

<template>
  <AdminModalShell
    aria-label="新增用户"
    :description="editingUserId ? '更新用户名称、角色和头像信息。' : '配置账号基本信息。'"
    :title="editingUserId ? '修改用户' : '新增用户'"
    @close="emit('close')"
  >
    <div class="modal-form single">
      <AdminFormField label="用户名">
        <input v-model="username" class="ui-input modal-control" type="text" placeholder="请输入用户名" />
      </AdminFormField>
      <AdminFormField v-if="!editingUserId" label="密码">
        <input v-model="password" class="ui-input modal-control" type="password" placeholder="设置初始密码" />
      </AdminFormField>
      <AdminFormField label="角色">
        <select v-model="role" class="ui-input modal-control">
          <option value="user">成员</option>
          <option value="admin">管理员</option>
        </select>
      </AdminFormField>
      <AdminFormField label="头像" hint="当前后端暂未保存头像，仅保存用户名、密码和角色。">
        <input v-model="avatarUrl" class="ui-input modal-control" type="text" placeholder="可选，填写头像 URL" />
      </AdminFormField>
    </div>
    <template #actions>
      <button class="ghost-btn" type="button" @click="emit('close')">取消</button>
      <button
        class="primary-btn"
        type="button"
        :disabled="!username.trim() || (!editingUserId && !password.trim())"
        @click="emit('save')"
      >
        {{ editingUserId ? "保存" : "创建" }}
      </button>
    </template>
  </AdminModalShell>
</template>
