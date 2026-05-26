<script setup lang="ts">
import { computed } from "vue";
import { NDrawer, NDrawerContent, NSpace, NTag, NText } from "naive-ui";

import { useAuthStore } from "@/stores/auth";
import { useChatStore } from "@/stores/chat";

const chat = useChatStore();
const auth = useAuthStore();

const roleTags = computed(() => auth.user?.roles ?? []);
</script>

<template>
  <n-drawer
    v-model:show="chat.drawerOpen"
    :width="420"
    placement="right"
    mask-closable
  >
    <n-drawer-content title="智能对话" closable>
      <n-text depth="3">
        对话功能将在后续任务中接入 SSE 与历史记录。
      </n-text>

      <n-space v-if="auth.user" vertical style="margin-top: 20px" :size="12">
        <n-space align="center">
          <n-text>用户 ID：</n-text>
          <n-text code>{{ auth.user.user_id }}</n-text>
        </n-space>
        <n-space v-if="roleTags.length" align="center" wrap>
          <n-text>当前角色：</n-text>
          <n-tag
            v-for="role in roleTags"
            :key="role.role_id"
            size="small"
            round
          >
            {{ role.role_id }}
          </n-tag>
        </n-space>
      </n-space>
    </n-drawer-content>
  </n-drawer>
</template>
