<script setup lang="ts">
import axios from "axios";
import { computed, h, onMounted, ref } from "vue";
import {
  NButton,
  NDataTable,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NPopconfirm,
  NSelect,
  NSpace,
  NTag,
  useMessage,
  type DataTableColumns,
} from "naive-ui";

import {
  createUser,
  deleteUser,
  fetchRoles,
  fetchUsers,
  updateUser,
} from "@/api/admin";
import type { AdminRole, AdminUser, ApiErrorBody } from "@/types";

const ADMIN_USER_ID = "u-admin";
const message = useMessage();

const loading = ref(false);
const users = ref<AdminUser[]>([]);
const roleOptions = ref<{ label: string; value: string }[]>([]);

const drawerVisible = ref(false);
const editing = ref<AdminUser | null>(null);
const formLoading = ref(false);
const formUsername = ref("");
const formPassword = ref("");
const formDisplayName = ref("");
const formRoleIds = ref<string[]>([]);

const columns = computed<DataTableColumns<AdminUser>>(() => [
  { title: "用户名", key: "username", width: 120 },
  { title: "显示名", key: "display_name", width: 120 },
  {
    title: "角色",
    key: "roles",
    minWidth: 200,
    render: (row) =>
      h(
        NSpace,
        { size: 4 },
        () =>
          row.roles.map((role) =>
            h(NTag, { size: "small", round: true }, { default: () => role.name }),
          ),
      ),
  },
  {
    title: "管理员",
    key: "is_admin",
    width: 90,
    render: (row) =>
      row.is_admin || row.role_ids.includes("role-admin") ? "是" : "否",
  },
  {
    title: "操作",
    key: "actions",
    width: 160,
    render: (row) =>
      h(NSpace, { size: "small" }, () => [
        h(
          NButton,
          { size: "small", quaternary: true, type: "primary", onClick: () => openEdit(row) },
          { default: () => "编辑" },
        ),
        row.user_id === ADMIN_USER_ID
          ? null
          : h(
              NPopconfirm,
              { onPositiveClick: () => onDelete(row.user_id) },
              {
                trigger: () =>
                  h(
                    NButton,
                    { size: "small", quaternary: true, type: "error" },
                    { default: () => "删除" },
                  ),
                default: () => `确定删除用户「${row.username}」吗？`,
              },
            ),
      ]),
  },
]);

async function loadRoleOptions(): Promise<void> {
  try {
    const roles = await fetchRoles();
    roleOptions.value = roles.map((role: AdminRole) => ({
      label: `${role.name} (${role.role_id})`,
      value: role.role_id,
    }));
  } catch {
    roleOptions.value = [];
  }
}

async function loadUsers(): Promise<void> {
  loading.value = true;
  try {
    users.value = await fetchUsers();
  } catch {
    message.error("加载用户列表失败");
  } finally {
    loading.value = false;
  }
}

function resetForm(): void {
  formUsername.value = "";
  formPassword.value = "";
  formDisplayName.value = "";
  formRoleIds.value = [];
}

function openCreate(): void {
  editing.value = null;
  resetForm();
  drawerVisible.value = true;
}

function openEdit(row: AdminUser): void {
  editing.value = row;
  formUsername.value = row.username;
  formPassword.value = "";
  formDisplayName.value = row.display_name;
  formRoleIds.value = [...row.role_ids];
  drawerVisible.value = true;
}

function extractFieldErrors(error: unknown): Record<string, string> {
  if (axios.isAxiosError(error) && error.response?.data) {
    const body = error.response.data as ApiErrorBody;
    return body.field_errors ?? {};
  }
  return {};
}

async function onSubmit(): Promise<void> {
  if (!editing.value && !formUsername.value.trim()) {
    message.warning("请填写用户名");
    return;
  }
  if (!formDisplayName.value.trim()) {
    message.warning("请填写显示名");
    return;
  }
  if (!editing.value && !formPassword.value.trim()) {
    message.warning("请填写密码");
    return;
  }
  if (formRoleIds.value.length === 0) {
    message.warning("请至少选择一个角色");
    return;
  }

  formLoading.value = true;
  try {
    if (editing.value) {
      const payload: {
        display_name: string;
        role_ids: string[];
        password?: string;
      } = {
        display_name: formDisplayName.value.trim(),
        role_ids: formRoleIds.value,
      };
      if (formPassword.value.trim()) {
        payload.password = formPassword.value.trim();
      }
      await updateUser(editing.value.user_id, payload);
      message.success("用户已更新");
    } else {
      await createUser({
        username: formUsername.value.trim(),
        password: formPassword.value.trim(),
        display_name: formDisplayName.value.trim(),
        role_ids: formRoleIds.value,
      });
      message.success("用户已创建");
    }
    drawerVisible.value = false;
    await loadUsers();
  } catch (error: unknown) {
    const fieldErrors = extractFieldErrors(error);
    if (fieldErrors.username) {
      message.error(`用户名：${fieldErrors.username}`);
    } else if (fieldErrors.role_ids) {
      message.error(`角色：${fieldErrors.role_ids}`);
    } else if (axios.isAxiosError(error) && error.response?.data) {
      const body = error.response.data as ApiErrorBody;
      message.error(body.message || "保存失败");
    } else {
      message.error("保存失败");
    }
  } finally {
    formLoading.value = false;
  }
}

async function onDelete(userId: string): Promise<void> {
  try {
    await deleteUser(userId);
    message.success("已删除");
    await loadUsers();
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && error.response?.data) {
      const body = error.response.data as ApiErrorBody;
      message.error(body.message || "删除失败");
    } else {
      message.error("删除失败");
    }
  }
}

onMounted(async () => {
  await loadRoleOptions();
  await loadUsers();
});
</script>

<template>
  <div class="users-page">
    <n-space vertical :size="16">
      <n-space justify="space-between" align="center">
        <span class="page-title">用户管理</span>
        <n-button type="primary" @click="openCreate">新建用户</n-button>
      </n-space>

      <n-data-table
        :columns="columns"
        :data="users"
        :loading="loading"
        :row-key="(row: AdminUser) => row.user_id"
      />
    </n-space>

    <n-drawer v-model:show="drawerVisible" :width="420" placement="right">
      <n-drawer-content :title="editing ? '编辑用户' : '新建用户'" closable>
        <n-form label-placement="top">
          <n-form-item label="用户名" required>
            <n-input
              v-model:value="formUsername"
              placeholder="登录用户名"
              :disabled="Boolean(editing)"
            />
          </n-form-item>
          <n-form-item :label="editing ? '新密码（留空不改）' : '密码'" :required="!editing">
            <n-input
              v-model:value="formPassword"
              type="password"
              show-password-on="click"
              placeholder="登录密码"
            />
          </n-form-item>
          <n-form-item label="显示名" required>
            <n-input v-model:value="formDisplayName" placeholder="界面显示名称" />
          </n-form-item>
          <n-form-item label="角色" required>
            <n-select
              v-model:value="formRoleIds"
              :options="roleOptions"
              multiple
              filterable
              placeholder="至少选择一个角色"
            />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="drawerVisible = false">取消</n-button>
            <n-button type="primary" :loading="formLoading" @click="onSubmit">
              保存
            </n-button>
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.users-page {
  width: 100%;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
}
</style>
