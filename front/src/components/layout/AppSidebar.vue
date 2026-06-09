<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NMenu } from "naive-ui";
import type { MenuOption } from "naive-ui";

import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const menuOptions = computed<MenuOption[]>(() => {
  const items: MenuOption[] = [
    { label: "首页", key: "/app/home" },
    { label: "学生管理", key: "/app/students" },
    { label: "通话", key: "/app/calls" },
  ];

  if (auth.isAdmin) {
    items.push(
      { type: "divider", key: "admin-divider" },
      { label: "角色管理", key: "/app/admin/roles" },
      { label: "用户管理", key: "/app/admin/users" },
      { label: "RAG 管理", key: "/app/admin/kb" },
    );
  }

  return items;
});

const activeKey = computed(() => route.path);

function onMenuUpdate(key: string): void {
  if (key.startsWith("/app")) {
    void router.push(key);
  }
}
</script>

<template>
  <n-menu
    class="app-menu"
    :value="activeKey"
    :options="menuOptions"
    @update:value="onMenuUpdate"
  />
</template>

<style scoped>
.app-menu {
  padding: 12px 10px;
}

.app-menu :deep(.n-menu-item-content) {
  height: 38px;
  margin: 2px 0;
  border-radius: 8px;
  color: #475569;
}

.app-menu :deep(.n-menu-item-content:hover) {
  background: #f1f5f9;
}

.app-menu :deep(.n-menu-item-content--selected) {
  color: #1d4ed8;
  background: #eff6ff;
  font-weight: 600;
}
</style>
