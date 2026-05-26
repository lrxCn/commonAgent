<script setup lang="ts">
import { computed } from "vue";
import { NCard, NH2, NSpace, NTag, NText } from "naive-ui";

import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();

const greeting = computed(() => {
  const hour = new Date().getHours();
  if (hour < 12) return "上午好";
  if (hour < 18) return "下午好";
  return "晚上好";
});

const displayName = computed(
  () => auth.user?.display_name || auth.user?.username || "用户",
);
</script>

<template>
  <n-card>
    <n-h2>{{ greeting }}，{{ displayName }}</n-h2>
    <n-text depth="3">欢迎使用 commonAgent 演示平台</n-text>

    <n-space v-if="auth.user" style="margin-top: 20px" align="center">
      <n-text>当前账号：</n-text>
      <n-text strong>{{ auth.user.username }}</n-text>
      <n-text v-if="auth.user.is_admin" depth="3">（管理员）</n-text>
    </n-space>

    <n-space v-if="auth.user?.roles.length" style="margin-top: 16px" align="center">
      <n-text>绑定角色：</n-text>
      <n-tag
        v-for="role in auth.user.roles"
        :key="role.role_id"
        type="info"
        size="small"
        round
      >
        {{ role.name }} ({{ role.role_id }})
      </n-tag>
    </n-space>

    <n-text v-else depth="3" style="display: block; margin-top: 16px">
      暂无绑定角色
    </n-text>
  </n-card>
</template>
