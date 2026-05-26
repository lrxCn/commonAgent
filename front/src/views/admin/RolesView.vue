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
  NSpace,
  useMessage,
  type DataTableColumns,
} from "naive-ui";

import { createRole, deleteRole, fetchRoles, updateRole } from "@/api/admin";
import type { AdminRole, ApiErrorBody } from "@/types";

const message = useMessage();

const loading = ref(false);
const roles = ref<AdminRole[]>([]);

const drawerVisible = ref(false);
const editing = ref<AdminRole | null>(null);
const formLoading = ref(false);
const formRoleId = ref("");
const formName = ref("");
const formDescription = ref("");

const columns = computed<DataTableColumns<AdminRole>>(() => [
  { title: "角色 ID", key: "role_id", width: 160 },
  { title: "名称", key: "name", width: 120 },
  {
    title: "描述",
    key: "description",
    ellipsis: { tooltip: true },
    render: (row) => row.description || "—",
  },
  { title: "用户数", key: "user_count", width: 90 },
  { title: "文档数", key: "document_count", width: 90 },
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
        h(
          NPopconfirm,
          { onPositiveClick: () => onDelete(row.role_id) },
          {
            trigger: () =>
              h(NButton, { size: "small", quaternary: true, type: "error" }, { default: () => "删除" }),
            default: () => `确定删除角色「${row.name}」吗？`,
          },
        ),
      ]),
  },
]);

async function loadRoles(): Promise<void> {
  loading.value = true;
  try {
    roles.value = await fetchRoles();
  } catch {
    message.error("加载角色列表失败");
  } finally {
    loading.value = false;
  }
}

function resetForm(): void {
  formRoleId.value = "";
  formName.value = "";
  formDescription.value = "";
}

function openCreate(): void {
  editing.value = null;
  resetForm();
  drawerVisible.value = true;
}

function openEdit(row: AdminRole): void {
  editing.value = row;
  formRoleId.value = row.role_id;
  formName.value = row.name;
  formDescription.value = row.description ?? "";
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
  if (!formName.value.trim()) {
    message.warning("请填写角色名称");
    return;
  }
  if (!editing.value && !formRoleId.value.trim()) {
    message.warning("请填写角色 ID");
    return;
  }

  formLoading.value = true;
  try {
    const description = formDescription.value.trim() || null;
    if (editing.value) {
      await updateRole(editing.value.role_id, {
        name: formName.value.trim(),
        description,
      });
      message.success("角色已更新");
    } else {
      await createRole({
        role_id: formRoleId.value.trim(),
        name: formName.value.trim(),
        description,
      });
      message.success("角色已创建");
    }
    drawerVisible.value = false;
    await loadRoles();
  } catch (error: unknown) {
    const fieldErrors = extractFieldErrors(error);
    if (fieldErrors.role_id) {
      message.error(`角色 ID：${fieldErrors.role_id}`);
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

async function onDelete(roleId: string): Promise<void> {
  try {
    await deleteRole(roleId);
    message.success("已删除");
    await loadRoles();
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && error.response?.data) {
      const body = error.response.data as ApiErrorBody;
      message.error(body.message || "删除失败");
    } else {
      message.error("删除失败");
    }
  }
}

onMounted(() => {
  void loadRoles();
});
</script>

<template>
  <div class="roles-page">
    <n-space vertical :size="16">
      <n-space justify="space-between" align="center">
        <span class="page-title">角色管理</span>
        <n-button type="primary" @click="openCreate">新建角色</n-button>
      </n-space>

      <n-data-table
        :columns="columns"
        :data="roles"
        :loading="loading"
        :row-key="(row: AdminRole) => row.role_id"
      />
    </n-space>

    <n-drawer v-model:show="drawerVisible" :width="420" placement="right">
      <n-drawer-content :title="editing ? '编辑角色' : '新建角色'" closable>
        <n-form label-placement="top">
          <n-form-item label="角色 ID" required>
            <n-input
              v-model:value="formRoleId"
              placeholder="例如 role-marketing"
              :disabled="Boolean(editing)"
            />
          </n-form-item>
          <n-form-item label="名称" required>
            <n-input v-model:value="formName" placeholder="角色显示名称" />
          </n-form-item>
          <n-form-item label="描述">
            <n-input
              v-model:value="formDescription"
              type="textarea"
              placeholder="可选描述"
              :autosize="{ minRows: 2, maxRows: 4 }"
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
.roles-page {
  width: 100%;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
}
</style>
