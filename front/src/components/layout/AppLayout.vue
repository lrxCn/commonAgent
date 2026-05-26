<script setup lang="ts">
import { useRouter } from "vue-router";
import {
  NButton,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NLayoutSider,
  NSpace,
  NText,
} from "naive-ui";

import ChatDrawer from "@/components/chat/ChatDrawer.vue";
import ChatFab from "@/components/chat/ChatFab.vue";
import AppSidebar from "@/components/layout/AppSidebar.vue";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();

async function onLogout(): Promise<void> {
  await auth.logout();
  await router.replace("/login");
}
</script>

<template>
  <n-layout has-sider style="min-height: 100vh">
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="220"
      show-trigger
    >
      <div class="brand">commonAgent</div>
      <app-sidebar />
    </n-layout-sider>

    <n-layout>
      <n-layout-header bordered class="app-header">
        <n-space align="center" justify="space-between" style="width: 100%">
          <n-text strong>演示平台</n-text>
          <n-space align="center">
            <n-text>{{ auth.user?.display_name || auth.user?.username }}</n-text>
            <n-button size="small" quaternary @click="onLogout">退出</n-button>
          </n-space>
        </n-space>
      </n-layout-header>

      <n-layout-content class="app-content">
        <router-view />
      </n-layout-content>
    </n-layout>

    <chat-fab />
    <chat-drawer />
  </n-layout>
</template>

<style scoped>
.brand {
  padding: 16px;
  font-weight: 600;
  font-size: 15px;
  border-bottom: 1px solid var(--n-border-color);
}

.app-header {
  height: 56px;
  padding: 0 20px;
  display: flex;
  align-items: center;
}

.app-content {
  padding: 20px;
  background: #f5f7fa;
  min-height: calc(100vh - 56px);
}
</style>
