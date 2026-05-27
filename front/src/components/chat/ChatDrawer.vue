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

import CreateStudentFormCard from "@/components/chat/CreateStudentFormCard.vue";
import JumpPageConfirmCard from "@/components/chat/JumpPageConfirmCard.vue";
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
  messageListRef.value?.scrollTo({
    top: Number.MAX_SAFE_INTEGER,
    behavior: "auto",
  });
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
    <n-drawer-content
      title="智能对话"
      closable
      :body-content-style="{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        padding: '0 20px 16px',
        boxSizing: 'border-box',
      }"
    >
      <div class="chat-drawer">
        <div class="chat-drawer__top">
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
          class="chat-error"
          @close="chat.clearError()"
        >
          {{ chat.error }}
        </n-alert>
        </div>

        <n-spin :show="chat.loadingHistory" class="chat-drawer__messages">
          <n-scrollbar ref="messageListRef" class="chat-messages">
            <p v-if="!chat.messages.length && !chat.loadingHistory" class="chat-empty">
              发送消息开始对话。可尝试「打开学生管理」跳转页面，或「新建学生张三，学号 2025001」「查学生列表」。
            </p>
            <article
              v-for="msg in chat.messages"
              :key="msg.id"
              class="chat-entry"
              :class="`chat-entry--${msg.role}`"
            >
              <div class="chat-bubble">
                <strong class="chat-entry__label">{{ roleLabel(msg.role) }}</strong>
                <JumpPageConfirmCard
                  v-if="msg.jumpPagePrompt"
                  :page-label="msg.jumpPagePrompt.pageLabel"
                  :status="msg.jumpPagePrompt.status"
                  :status-detail="msg.jumpPagePrompt.statusDetail"
                  @confirm="() => void chat.confirmJumpPage(msg.id)"
                  @cancel="chat.cancelJumpPage(msg.id)"
                />
                <CreateStudentFormCard
                  v-else-if="msg.createStudentForm"
                  :prefill="msg.createStudentForm.prefill"
                  :status="msg.createStudentForm.status"
                  :error-detail="msg.createStudentForm.errorDetail"
                  :field-errors="msg.createStudentForm.fieldErrors"
                  :created-student="msg.createStudentForm.createdStudent"
                  @submit="(payload) => void chat.submitCreateStudentForm(msg.id, payload)"
                  @cancel="chat.cancelCreateStudentForm(msg.id)"
                />
                <p
                  v-else-if="msg.content || msg.streaming"
                  class="chat-entry__content"
                >
                  {{ msg.content }}<span v-if="msg.streaming" class="chat-cursor">▍</span>
                </p>
              </div>
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
  flex: 1;
  min-height: 0;
  height: 100%;
}

.chat-drawer__top {
  flex-shrink: 0;
}

.chat-meta {
  flex-shrink: 0;
}

.chat-error {
  margin-top: 12px;
}

.chat-drawer__messages {
  flex: 1;
  min-height: 0;
  margin-top: 12px;
}

.chat-drawer__messages :deep(.n-spin-container),
.chat-drawer__messages :deep(.n-spin-content) {
  height: 100%;
  min-height: 0;
}

.chat-messages {
  height: 100%;
  padding: 8px 4px;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  background: #fafafa;
  --chat-human-bg: #2563eb;
  --chat-human-text: #ffffff;
  --chat-human-label: rgba(255, 255, 255, 0.38);
  --chat-ai-bg: #ffffff;
  --chat-ai-border: #e5e7eb;
  --chat-ai-text: #374151;
  --chat-ai-label: #d8dce3;
}

.chat-empty {
  margin: 0;
  color: var(--n-text-color-3);
  font-size: 13px;
}

.chat-entry {
  display: flex;
  margin-bottom: 12px;
}

.chat-entry--human {
  justify-content: flex-end;
}

.chat-entry--ai {
  justify-content: flex-start;
}

.chat-entry--system {
  justify-content: center;
}

.chat-bubble {
  max-width: 88%;
  padding: 8px 12px;
  border-radius: 12px;
}

.chat-entry__label {
  display: block;
  margin-bottom: 4px;
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.02em;
}

.chat-entry__content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.55;
}

.chat-entry--human .chat-bubble {
  background: var(--chat-human-bg);
  border-bottom-right-radius: 4px;
  box-shadow: 0 1px 2px rgba(37, 99, 235, 0.18);
}

.chat-entry--human .chat-entry__label {
  text-align: right;
  color: var(--chat-human-label);
}

.chat-entry--human .chat-entry__content {
  color: var(--chat-human-text);
}

.chat-entry--ai .chat-bubble {
  background: var(--chat-ai-bg);
  border: 1px solid var(--chat-ai-border);
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.chat-entry--ai .chat-entry__label {
  text-align: left;
  color: var(--chat-ai-label);
}

.chat-entry--ai .chat-entry__content {
  color: var(--chat-ai-text);
}

.chat-entry--system .chat-bubble {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
}

.chat-entry--system .chat-entry__label {
  text-align: center;
  color: #e8d4b8;
}

.chat-entry--system .chat-entry__content {
  color: #78350f;
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
  flex-shrink: 0;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--n-border-color);
  background: var(--n-color-modal);
}
</style>
