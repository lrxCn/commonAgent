<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import {
  NAlert,
  NButton,
  NDrawer,
  NDrawerContent,
  NInput,
  NScrollbar,
  NSpace,
  NSpin,
  NTag,
  NText,
} from "naive-ui";

import { useAuthStore } from "@/stores/auth";
import { useChatStore } from "@/stores/chat";

const chat = useChatStore();
const auth = useAuthStore();

const draft = ref("");
const messageListRef = ref<InstanceType<typeof NScrollbar> | null>(null);

const roleTags = computed(() => auth.user?.roles ?? []);
const canSend = computed(() => draft.value.trim().length > 0 && !chat.sending);

function roleLabel(role: string): string {
  if (role === "human") {
    return "你";
  }
  if (role === "ai") {
    return "助手";
  }
  return "系统";
}

async function scrollToBottom(): Promise<void> {
  await nextTick();
  const el = messageListRef.value?.$el?.querySelector(".n-scrollbar-container");
  if (el instanceof HTMLElement) {
    el.scrollTop = el.scrollHeight;
  }
}

watch(
  () => chat.messages.length,
  () => {
    void scrollToBottom();
  },
);

watch(
  () => chat.messages.at(-1)?.content,
  () => {
    void scrollToBottom();
  },
);

function handleSend(): void {
  const text = draft.value.trim();
  if (!text) {
    return;
  }
  draft.value = "";
  void chat.sendMessage(text);
}

function handleDrawerUpdate(show: boolean): void {
  if (show) {
    chat.openDrawer();
  } else {
    chat.closeDrawer();
  }
}
</script>

<template>
  <n-drawer
    :show="chat.drawerOpen"
    :width="420"
    placement="right"
    mask-closable
    @update:show="handleDrawerUpdate"
  >
    <n-drawer-content title="智能对话" closable>
      <div class="chat-drawer">
        <n-space vertical :size="8" class="chat-meta">
          <n-space align="center" wrap :size="8">
            <n-text depth="3">thread_id</n-text>
            <n-text code>{{ chat.threadId }}</n-text>
            <n-button size="tiny" quaternary @click="() => void chat.copyThreadId()">
              复制
            </n-button>
            <n-button size="tiny" @click="chat.startNewThread()">
              新开 thread
            </n-button>
          </n-space>
          <n-space v-if="roleTags.length" align="center" wrap :size="8">
            <n-text depth="3">当前角色</n-text>
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

        <n-alert
          v-if="chat.error"
          type="error"
          closable
          style="margin-top: 12px"
          @close="chat.clearError()"
        >
          {{ chat.error }}
        </n-alert>

        <n-spin :show="chat.loadingHistory" style="margin-top: 12px">
          <n-scrollbar ref="messageListRef" class="chat-messages">
            <p v-if="!chat.messages.length && !chat.loadingHistory" class="chat-empty">
              发送消息开始对话。client_actions 将输出到浏览器 Console。
            </p>
            <article
              v-for="msg in chat.messages"
              :key="msg.id"
              class="chat-entry"
              :class="`chat-entry--${msg.role}`"
            >
              <strong>{{ roleLabel(msg.role) }}</strong>
              <p>
                {{ msg.content }}<span v-if="msg.streaming" class="chat-cursor">▍</span>
              </p>
            </article>
          </n-scrollbar>
        </n-spin>

        <form class="chat-input" @submit.prevent="handleSend">
          <n-input
            v-model:value="draft"
            type="textarea"
            placeholder="输入消息…"
            :autosize="{ minRows: 2, maxRows: 4 }"
            :disabled="chat.sending"
            @keydown.enter.exact.prevent="handleSend"
          />
          <n-button
            type="primary"
            attr-type="submit"
            :loading="chat.sending"
            :disabled="!canSend"
          >
            发送
          </n-button>
        </form>
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<style scoped>
.chat-drawer {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  min-height: 320px;
}

.chat-meta {
  flex-shrink: 0;
}

.chat-messages {
  flex: 1;
  min-height: 180px;
  max-height: calc(100vh - 320px);
  padding: 8px 4px;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  background: var(--n-color-modal);
}

.chat-empty {
  margin: 0;
  color: var(--n-text-color-3);
  font-size: 13px;
}

.chat-entry {
  margin-bottom: 12px;
}

.chat-entry strong {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--n-text-color-3);
}

.chat-entry p {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-entry--human p {
  color: var(--n-text-color);
}

.chat-entry--ai p {
  color: var(--n-text-color);
}

.chat-cursor {
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.chat-input {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
  flex-shrink: 0;
}
</style>
