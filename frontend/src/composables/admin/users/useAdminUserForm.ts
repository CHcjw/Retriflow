import { shallowRef } from "vue";

import type { AdminUserCreateRequest, AdminUserItem, AdminUserUpdateRequest } from "../../../services/adminApi";

export function useAdminUserForm() {
  const editingUserId = shallowRef("");
  const newAdminUsername = shallowRef("");
  const newAdminPassword = shallowRef("");
  const newAdminRole = shallowRef("user");
  const newAdminAvatarUrl = shallowRef("");

  function resetUserForm() {
    editingUserId.value = "";
    newAdminUsername.value = "";
    newAdminPassword.value = "";
    newAdminRole.value = "user";
    newAdminAvatarUrl.value = "";
  }

  function fillUserForm(user: AdminUserItem) {
    editingUserId.value = user.id;
    newAdminUsername.value = user.username;
    newAdminPassword.value = "";
    newAdminRole.value = user.role;
    newAdminAvatarUrl.value = user.avatar_url;
  }

  function buildUserCreatePayload(): AdminUserCreateRequest {
    return {
      username: newAdminUsername.value.trim(),
      password: newAdminPassword.value,
      role: newAdminRole.value
    };
  }

  function buildUserUpdatePayload(): AdminUserUpdateRequest {
    return {
      username: newAdminUsername.value.trim(),
      role: newAdminRole.value,
      avatar_url: newAdminAvatarUrl.value.trim()
    };
  }

  return {
    editingUserId,
    newAdminUsername,
    newAdminPassword,
    newAdminRole,
    newAdminAvatarUrl,
    resetUserForm,
    fillUserForm,
    buildUserCreatePayload,
    buildUserUpdatePayload
  };
}
