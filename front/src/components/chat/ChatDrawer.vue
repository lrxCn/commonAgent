<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NDrawer,
  NDrawerContent,
  NInput,
  NScrollbar,
  NSpin,
  NTag,
  NText
} from 'naive-ui'

import CreateStudentFormCard from '@/components/chat/CreateStudentFormCard.vue'
import JumpPageConfirmCard from '@/components/chat/JumpPageConfirmCard.vue'
import StudentListCard from '@/components/chat/StudentListCard.vue'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()
const auth = useAuthStore()

const draft = ref('')
const messageListRef = ref<InstanceType<typeof NScrollbar> | null>(null)

const roleTags = computed(() => auth.user?.roles ?? [])
const canSend = computed(() => draft.value.trim().length > 0 && !chat.sending)
const quickPrompts = [
  '帮我添加一个学生',
  '查学生列表',
  '打开学生管理',
  '新建学生张三，学号 2025001'
]

function roleLabel(role: string): string {
  if (role === 'human') {
    return '你'
  }
  if (role === 'ai') {
    return '助手'
  }
  return '系统'
}

function roleAvatar(role: string): string {
  if (role === 'human') {
    return '你'
  }
  if (role === 'ai') {
    return 'AI'
  }
  return '!'
}

function hasMessageBody(msg: {
  content: string
  streaming?: boolean
}): boolean {
  return Boolean(msg.content || msg.streaming)
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  messageListRef.value?.scrollTo({
    top: Number.MAX_SAFE_INTEGER,
    behavior: 'auto'
  })
}

watch(
  () => chat.messages.length,
  () => {
    void scrollToBottom()
  }
)

watch(
  () => chat.messages.at(-1)?.content,
  () => {
    void scrollToBottom()
  }
)

function handleSend(): void {
  const text = draft.value.trim()
  if (!text) {
    return
  }
  draft.value = ''
  void chat.sendMessage(text)
}

function sendQuickPrompt(text: string): void {
  if (chat.sending) {
    return
  }
  draft.value = ''
  void chat.sendMessage(text)
}

function handleDrawerUpdate(show: boolean): void {
  if (show) {
    chat.openDrawer()
  } else {
    chat.closeDrawer()
  }
}
</script>

<template>
  <n-drawer
    :show="chat.drawerOpen"
    :width="500"
    placement="right"
    mask-closable
    @update:show="handleDrawerUpdate"
  >
    <n-drawer-content
      closable
      :body-content-style="{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        padding: '0',
        boxSizing: 'border-box'
      }"
      :header-style="{ padding: '0' }"
    >
      <template #header>
        <header class="chat-header">
          <div class="chat-header__main">
            <span class="chat-header__avatar">AI</span>
            <div class="chat-header__copy">
              <strong>智能对话</strong>
              <span>在线处理页面跳转、学生创建和列表查询</span>
            </div>
          </div>
          <div class="chat-header__actions">
            <n-button
              size="tiny"
              quaternary
              @click="() => void chat.copyThreadId()"
            >
              复制
            </n-button>
            <n-button size="tiny" secondary @click="chat.startNewThread()">
              新会话
            </n-button>
          </div>
        </header>
      </template>

      <div class="chat-drawer">
        <section class="chat-context">
          <div class="chat-context__row">
            <span class="chat-context__label">Thread</span>
            <n-text code class="chat-context__thread">
              {{ chat.threadId }}
            </n-text>
          </div>
          <div v-if="roleTags.length" class="chat-context__roles">
            <span class="chat-context__label">角色</span>
            <n-tag
              v-for="role in roleTags"
              :key="role.role_id"
              size="small"
              round
            >
              {{ role.role_id }}
            </n-tag>
          </div>
        </section>

        <n-alert
          v-if="chat.error"
          type="error"
          closable
          class="chat-error"
          @close="chat.clearError()"
        >
          {{ chat.error }}
        </n-alert>

        <n-spin :show="chat.loadingHistory" class="chat-drawer__messages">
          <n-scrollbar ref="messageListRef" class="chat-messages">
            <div
              v-if="!chat.messages.length && !chat.loadingHistory"
              class="chat-empty"
            >
              <div class="chat-empty__icon">AI</div>
              <strong>可以直接输入业务指令</strong>
              <p>例如创建学生、查看学生列表，或跳转到后台页面。</p>
            </div>
            <article
              v-for="msg in chat.messages"
              :key="msg.id"
              class="chat-entry"
              :class="`chat-entry--${msg.role}`"
            >
              <span v-if="msg.role !== 'human'" class="chat-entry__avatar">
                {{ roleAvatar(msg.role) }}
              </span>
              <div class="chat-entry__stack">
                <span v-if="msg.role !== 'human'" class="chat-entry__name">
                  {{ roleLabel(msg.role) }}
                </span>
                <div v-if="hasMessageBody(msg)" class="chat-bubble">
                  <p class="chat-entry__content">
                    {{ msg.content }}
                    <span v-if="msg.streaming" class="chat-cursor">▍</span>
                  </p>
                </div>
                <div
                  v-if="
                    msg.jumpPagePrompt ||
                    msg.createStudentForm ||
                    msg.listStudents
                  "
                  class="chat-action-card"
                >
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
                    @submit="
                      payload =>
                        void chat.submitCreateStudentForm(msg.id, payload)
                    "
                    @cancel="chat.cancelCreateStudentForm(msg.id)"
                  />
                  <StudentListCard
                    v-else-if="msg.listStudents"
                    :query="msg.listStudents.query"
                    :status="msg.listStudents.status"
                    :data="msg.listStudents.data"
                    :error-detail="msg.listStudents.errorDetail"
                    @refresh="
                      query => void chat.refreshListStudents(msg.id, query)
                    "
                  />
                </div>
              </div>
            </article>
          </n-scrollbar>
        </n-spin>

        <footer class="chat-composer">
          <div class="chat-prompts">
            <button
              v-for="prompt in quickPrompts"
              :key="prompt"
              type="button"
              :disabled="chat.sending"
              @click="sendQuickPrompt(prompt)"
            >
              {{ prompt }}
            </button>
          </div>
          <form class="chat-input" @submit.prevent="handleSend">
            <n-input
              v-model:value="draft"
              type="textarea"
              placeholder="输入消息，Enter 发送，Shift+Enter 换行"
              :autosize="{ minRows: 1, maxRows: 4 }"
              :disabled="chat.sending"
              @keydown.enter.exact.prevent="handleSend"
            />
            <n-button
              type="primary"
              attr-type="submit"
              :loading="chat.sending"
              :disabled="!canSend"
              class="chat-input__send"
            >
              发送
            </n-button>
          </form>
        </footer>
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 14px 18px;
  border-bottom: 1px solid #e5e7eb;
  background: #ffffff;
  box-sizing: border-box;
}

.chat-header__main {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 10px;
}

.chat-header__avatar,
.chat-empty__icon,
.chat-entry__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-weight: 700;
}

.chat-header__avatar {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  color: #ffffff;
  background: #111827;
  font-size: 13px;
}

.chat-header__copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 2px;
}

.chat-header__copy strong {
  color: #111827;
  font-size: 15px;
  line-height: 1.3;
}

.chat-header__copy span {
  overflow: hidden;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-header__actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: 6px;
}

.chat-header__actions :deep(.n-button) {
  --n-border-radius: 7px !important;
}

.chat-drawer {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  height: 100%;
  background: #f3f6fa;
}

.chat-context {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  flex-shrink: 0;
  gap: 6px;
  padding: 10px 18px;
  border-bottom: 1px solid #e5e7eb;
  background: rgba(255, 255, 255, 0.86);
}

.chat-context__row,
.chat-context__roles {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 8px;
}

.chat-context__label {
  flex-shrink: 0;
  width: 44px;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 600;
}

.chat-context__thread {
  overflow: hidden;
  max-width: 100%;
  padding: 2px 6px;
  border-radius: 6px;
  background: #f1f5f9;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-error {
  flex-shrink: 0;
  margin: 12px 20px 0;
}

.chat-drawer__messages {
  flex: 1;
  min-height: 0;
}

.chat-drawer__messages :deep(.n-spin-container),
.chat-drawer__messages :deep(.n-spin-content) {
  height: 100%;
  min-height: 0;
}

.chat-messages {
  height: 100%;

  padding: 18px 22px 122px;
  --chat-human-bg: #2563eb;
  --chat-human-text: #ffffff;
  --chat-ai-bg: #ffffff;
  --chat-ai-border: #e5e7eb;
  --chat-ai-text: #1f2937;
  padding: 0 20px;
}

.chat-empty {
  display: flex;
  align-items: center;
  flex-direction: column;
  justify-content: center;
  min-height: 260px;
  margin: 0;
  color: #6b7280;
  text-align: center;
  font-size: 13px;
}

.chat-empty__icon {
  width: 42px;
  height: 42px;
  margin-bottom: 12px;
  border-radius: 14px;
  color: #ffffff;
  background: #111827;
  font-size: 14px;
}

.chat-empty strong {
  color: #111827;
  font-size: 15px;
}

.chat-empty p {
  max-width: 280px;
  margin: 6px 0 0;
  line-height: 1.5;
}

.chat-entry {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 16px;
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

.chat-entry__avatar {
  width: 30px;
  height: 30px;
  margin-top: 2px;
  border-radius: 9px;
  color: #ffffff;
  background: #111827;
  font-size: 11px;
}

.chat-entry--system .chat-entry__avatar {
  display: none;
}

.chat-entry__stack {
  display: flex;
  flex-direction: column;
  max-width: min(82%, 372px);
  gap: 5px;
}

.chat-entry--human .chat-entry__stack {
  align-items: flex-end;
}

.chat-entry--ai .chat-entry__stack {
  align-items: flex-start;
}

.chat-entry__name {
  display: block;
  padding: 0 3px;
  color: #9ca3af;
  font-size: 11px;
  font-weight: 400;
  line-height: 1.2;
}

.chat-bubble {
  max-width: 100%;
  padding: 9px 13px;
  border-radius: 14px;
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
  border-bottom-right-radius: 5px;
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.16);
}

.chat-entry--human .chat-entry__content {
  color: var(--chat-human-text);
}

.chat-entry--ai .chat-bubble {
  background: var(--chat-ai-bg);
  border: 1px solid var(--chat-ai-border);
  border-bottom-left-radius: 5px;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
}

.chat-entry--ai .chat-entry__content {
  color: var(--chat-ai-text);
}

.chat-entry--system .chat-bubble {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
}

.chat-entry--system .chat-entry__stack {
  align-items: center;
}

.chat-entry--system .chat-entry__content {
  color: #78350f;
}

.chat-action-card {
  width: min(100%, 360px);
}

.chat-entry--human .chat-action-card {
  display: none;
}

.chat-cursor {
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.chat-composer {
  flex-shrink: 0;
  padding: 10px 16px 14px;
  border-top: 1px solid #e5e7eb;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 -12px 28px rgba(15, 23, 42, 0.07);
}

.chat-prompts {
  display: flex;
  gap: 7px;
  overflow-x: auto;
  padding-bottom: 8px;
  scrollbar-width: none;
}

.chat-prompts::-webkit-scrollbar {
  display: none;
}

.chat-prompts button {
  flex: 0 0 auto;
  height: 30px;
  max-width: 180px;
  padding: 0 12px;
  overflow: hidden;
  border: 1px solid #d6e4ff;
  border-radius: 8px;
  color: #1f4fbf;
  background: #f7fbff;
  font: inherit;
  font-size: 12px;
  line-height: 28px;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  transition:
    color 0.15s ease,
    background-color 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.chat-prompts button:hover:not(:disabled) {
  border-color: #2563eb;
  color: #ffffff;
  background: #2563eb;
  box-shadow: 0 6px 14px rgba(37, 99, 235, 0.18);
}

.chat-prompts button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.chat-input {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.chat-input :deep(.n-input) {
  border-radius: 8px;
  --n-border-hover: 1px solid #93c5fd !important;
  --n-border-focus: 1px solid #2563eb !important;
  --n-box-shadow-focus: 0 0 0 2px rgba(37, 99, 235, 0.12) !important;
}

.chat-input__send {
  flex-shrink: 0;
  min-width: 66px;
  height: 38px;
  --n-color: #2563eb !important;
  --n-color-hover: #1d4ed8 !important;
  --n-color-pressed: #1e40af !important;
  --n-color-focus: #2563eb !important;
  --n-border: 1px solid #2563eb !important;
  --n-border-hover: 1px solid #1d4ed8 !important;
  --n-border-pressed: 1px solid #1e40af !important;
  --n-border-focus: 1px solid #2563eb !important;
  --n-border-radius: 8px !important;
  --n-font-weight: 600 !important;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.18);
}

@media (max-width: 560px) {
  .chat-header {
    align-items: flex-start;
    flex-direction: column;
    padding-right: 44px;
  }

  .chat-header__actions {
    width: 100%;
  }

  .chat-entry__stack {
    max-width: 88%;
  }
}
</style>
