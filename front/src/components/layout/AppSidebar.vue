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
  ];

  if (auth.isAdmin) {
    items.push(
      { type: "divider", key: "admin-divider" },
      { label: "角色管理", key: "/app/admin/roles" },
      { label: "用户管理", key: "/app/admin/users" },
      { label: "RAG 管理", key: "/app/admin/kb", disabled: true },
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
    :value="activeKey"
    :options="menuOptions"
    @update:value="onMenuUpdate"
  />
</template>
