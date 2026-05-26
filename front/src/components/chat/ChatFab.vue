<script setup lang="ts">
import { NButton } from "naive-ui";

import { useChatStore } from "@/stores/chat";

const chat = useChatStore();
</script>

<template>
  <n-button
    class="chat-fab"
    type="primary"
    circle
    size="large"
    aria-label="打开对话"
    @click="chat.openDrawer()"
  >
    对话
  </n-button>
</template>

<style scoped>
.chat-fab {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
</style>
