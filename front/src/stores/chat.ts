import { defineStore } from "pinia";
import { createDiscreteApi } from "naive-ui";
import { ref, watch } from "vue";

import * as chatApi from "@/api/chat";
import {
  formatCreateStudentPrefill,
  validateCreateStudentAction,
} from "@/client-actions/create-student";
import {
  isPageAllowedForUser,
  PAGE_SLUG_LABELS,
  parsePageSlug,
  resolveJumpPageTarget,
} from "@/client-actions/page-registry";
import { useAuthStore } from "@/stores/auth";
import { useStudentUiStore } from "@/stores/student-ui";
import type {
  ChatDisplayMessage,
  ClientAction,
  CreateStudentPrompt,
  CreateStudentPromptStatus,
  HistoryMessageItem,
  JumpPageArgs,
  JumpPagePrompt,
  JumpPagePromptStatus,
  PageSlug,
  StudentCreateRequest,
} from "@/types";

const THREAD_STORAGE_KEY = "common_agent_thread_id";
const LAST_USER_STORAGE_KEY = "common_agent_last_user_id";

const { message } = createDiscreteApi(["message"]);

type SseEvent = {
  type?: string;
  content?: string;
  segment_id?: string;
  client_actions?: ClientAction[];
  reason?: string;
};

type StreamingSegments = {
  order: string[];
  segments: Map<string, string>;
  plain: string;
};

function getOrCreateThreadId(): string {
  let id = sessionStorage.getItem(THREAD_STORAGE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(THREAD_STORAGE_KEY, id);
  }
  return id;
}

type JumpPageValidation =
  | { ok: true; slug: PageSlug; pageLabel: string }
  | { ok: false; pageLabel: string; detail: string };

function validateJumpPageAction(action: ClientAction): JumpPageValidation {
  const args = action.args as JumpPageArgs;
  const rawPage = typeof args.page === "string" ? args.page : "";
  const slug = parsePageSlug(rawPage);
  const fallbackLabel = rawPage.trim() || "未知页面";

  if (!slug) {
    return { ok: false, pageLabel: fallbackLabel, detail: "未知页面，无法跳转" };
  }

  const pageLabel = PAGE_SLUG_LABELS[slug];
  const auth = useAuthStore();
  if (!auth.isAuthenticated) {
    return { ok: false, pageLabel, detail: "请先登录后再跳转页面" };
  }
  if (!isPageAllowedForUser(slug, auth.isAdmin)) {
    return { ok: false, pageLabel, detail: "当前账号无权访问该页面" };
  }
  if (!resolveJumpPageTarget(rawPage)) {
    return { ok: false, pageLabel, detail: "未知页面，无法跳转" };
  }
  return { ok: true, slug, pageLabel };
}

function buildJumpPagePromptMessage(
  action: ClientAction,
  initialStatus: JumpPagePromptStatus,
): ChatDisplayMessage {
  const validation = validateJumpPageAction(action);
  const jumpPagePrompt: JumpPagePrompt = validation.ok
    ? {
        action,
        slug: validation.slug,
        pageLabel: validation.pageLabel,
        status: initialStatus,
      }
    : {
        action,
        slug: null,
        pageLabel: validation.pageLabel,
        status: "invalid",
        statusDetail: validation.detail,
      };

  return {
    id: crypto.randomUUID(),
    role: "ai",
    content: "",
    jumpPagePrompt,
  };
}

function buildCreateStudentPromptMessage(
  action: ClientAction,
  initialStatus: CreateStudentPromptStatus,
): ChatDisplayMessage {
  const validation = validateCreateStudentAction(action);
  const createStudentPrompt: CreateStudentPrompt = validation.ok
    ? {
        action,
        prefill: validation.args,
        prefillLines: formatCreateStudentPrefill(validation.args),
        status: initialStatus,
      }
    : {
        action,
        prefill: {},
        prefillLines: [],
        status: "invalid",
        statusDetail: validation.detail,
      };

  return {
    id: crypto.randomUUID(),
    role: "ai",
    content: "",
    createStudentPrompt,
  };
}

function historyToDisplayItems(item: HistoryMessageItem): ChatDisplayMessage[] {
  if (item.role === "tool" || item.role === "other") {
    return [];
  }

  const items: ChatDisplayMessage[] = [];
  const content = item.content?.trim() ?? "";
  if (content || item.role === "human") {
    items.push({
      id: item.message_id ?? crypto.randomUUID(),
      role: item.role,
      content: item.content,
    });
  }

  if (item.client_actions?.length) {
    for (const action of item.client_actions) {
      if (action.tool === "jumpPage") {
        items.push(buildJumpPagePromptMessage(action, "historical"));
      } else if (action.tool === "createStudent") {
        items.push(buildCreateStudentPromptMessage(action, "historical"));
      }
    }
  }

  return items;
}

function segmentsToText(state: StreamingSegments): string {
  if (state.order.length > 0) {
    return state.order.map((id) => state.segments.get(id) ?? "").join("");
  }
  return state.plain;
}

async function navigateJumpPage(action: ClientAction): Promise<boolean> {
  const args = action.args as JumpPageArgs;
  const rawPage = typeof args.page === "string" ? args.page : "";
  const validation = validateJumpPageAction(action);
  if (!validation.ok) {
    message.warning(validation.detail);
    return false;
  }

  const target = resolveJumpPageTarget(rawPage);
  if (!target) {
    message.warning("未知页面，无法跳转");
    return false;
  }

  const { default: router } = await import("@/router");
  try {
    await router.push(target);
    if (import.meta.env.DEV) {
      console.info("[client_actions] jumpPage navigated", {
        page: validation.slug,
        target,
      });
    }
    return true;
  } catch (err) {
    console.error("[client_actions] jumpPage navigation failed", err);
    message.warning("页面跳转失败");
    return false;
  }
}

async function executeCreateStudent(prefill: Partial<StudentCreateRequest>): Promise<boolean> {
  const auth = useAuthStore();
  if (!auth.isAuthenticated) {
    message.warning("请先登录后再新建学生");
    return false;
  }

  const studentUi = useStudentUiStore();
  studentUi.setPendingCreate(prefill);

  const { default: router } = await import("@/router");
  try {
    if (router.currentRoute.value.name !== "app-students") {
      await router.push({ name: "app-students" });
    }
    if (import.meta.env.DEV) {
      console.info("[client_actions] createStudent navigated", { prefill });
    }
    return true;
  } catch (err) {
    studentUi.clearPendingCreate();
    console.error("[client_actions] createStudent navigation failed", err);
    message.warning("打开新建学生表单失败");
    return false;
  }
}

export const useChatStore = defineStore("chat", () => {
  const drawerOpen = ref(false);
  const threadId = ref(getOrCreateThreadId());
  const messages = ref<ChatDisplayMessage[]>([]);
  const loadingHistory = ref(false);
  const sending = ref(false);
  const error = ref<string | null>(null);

  let streamAbort: AbortController | null = null;
  let streamingMessageId: string | null = null;
  let streamingSegments: StreamingSegments | null = null;

  function persistThreadId(id: string): void {
    threadId.value = id;
    sessionStorage.setItem(THREAD_STORAGE_KEY, id);
  }

  function abortStreaming(): void {
    streamAbort?.abort();
    streamAbort = null;
    if (streamingMessageId) {
      const msg = messages.value.find((item) => item.id === streamingMessageId);
      if (msg) {
        msg.streaming = false;
      }
    }
    streamingMessageId = null;
    streamingSegments = null;
  }

  function openDrawer(): void {
    drawerOpen.value = true;
  }

  function closeDrawer(): void {
    drawerOpen.value = false;
    abortStreaming();
  }

  function enqueueJumpPagePrompt(action: ClientAction): void {
    const promptMessage = buildJumpPagePromptMessage(action, "pending");
    messages.value.push(promptMessage);
    if (promptMessage.jumpPagePrompt?.status === "invalid") {
      message.warning(promptMessage.jumpPagePrompt.statusDetail ?? "无法跳转");
    }
    if (import.meta.env.DEV) {
      console.info("[client_actions] jumpPage prompt enqueued", action);
    }
  }

  function enqueueCreateStudentPrompt(action: ClientAction): void {
    const promptMessage = buildCreateStudentPromptMessage(action, "pending");
    messages.value.push(promptMessage);
    if (promptMessage.createStudentPrompt?.status === "invalid") {
      message.warning(promptMessage.createStudentPrompt.statusDetail ?? "无法打开新建学生表单");
    }
    if (import.meta.env.DEV) {
      console.info("[client_actions] createStudent prompt enqueued", action);
    }
  }

  function handleClientActions(actions: unknown): void {
    if (!Array.isArray(actions)) {
      console.warn("[client_actions] expected array, got", actions);
      return;
    }
    for (const action of actions) {
      if (!action || typeof action !== "object") {
        continue;
      }
      const record = action as ClientAction;
      if (record.tool === "jumpPage") {
        enqueueJumpPagePrompt(record);
        continue;
      }
      if (record.tool === "createStudent") {
        enqueueCreateStudentPrompt(record);
        continue;
      }

      const tool = record.tool ?? "(unknown)";
      const needsApproval = Boolean(record.requires_approval);
      const prompt = `执行工具「${tool}」？\n参数：${JSON.stringify(record.args ?? {}, null, 2)}`;
      if (needsApproval && !window.confirm(prompt)) {
        if (import.meta.env.DEV) {
          console.log("[client_actions] skipped (user declined)", action);
        }
        continue;
      }
      if (import.meta.env.DEV) {
        console.log("[client_actions] unhandled tool", action);
      }
    }
  }

  async function confirmJumpPage(messageId: string): Promise<void> {
    const entry = messages.value.find((item) => item.id === messageId);
    const prompt = entry?.jumpPagePrompt;
    if (!entry || !prompt || prompt.status !== "pending") {
      return;
    }

    const ok = await navigateJumpPage(prompt.action);
    if (ok) {
      prompt.status = "confirmed";
      closeDrawer();
    }
  }

  function cancelJumpPage(messageId: string): void {
    const entry = messages.value.find((item) => item.id === messageId);
    const prompt = entry?.jumpPagePrompt;
    if (!entry || !prompt || prompt.status !== "pending") {
      return;
    }
    prompt.status = "cancelled";
    if (import.meta.env.DEV) {
      console.log("[client_actions] jumpPage cancelled", prompt.action);
    }
  }

  async function confirmCreateStudent(messageId: string): Promise<void> {
    const entry = messages.value.find((item) => item.id === messageId);
    const prompt = entry?.createStudentPrompt;
    if (!entry || !prompt || prompt.status !== "pending") {
      return;
    }

    const validation = validateCreateStudentAction(prompt.action);
    if (!validation.ok) {
      prompt.status = "invalid";
      prompt.statusDetail = validation.detail;
      message.warning(validation.detail);
      return;
    }

    const ok = await executeCreateStudent(validation.args);
    if (ok) {
      prompt.status = "confirmed";
      closeDrawer();
    }
  }

  function cancelCreateStudent(messageId: string): void {
    const entry = messages.value.find((item) => item.id === messageId);
    const prompt = entry?.createStudentPrompt;
    if (!entry || !prompt || prompt.status !== "pending") {
      return;
    }
    prompt.status = "cancelled";
    if (import.meta.env.DEV) {
      console.log("[client_actions] createStudent cancelled", prompt.action);
    }
  }

  function toggleDrawer(): void {
    if (drawerOpen.value) {
      closeDrawer();
    } else {
      openDrawer();
    }
  }

  async function loadHistory(): Promise<void> {
    if (loadingHistory.value) {
      return;
    }
    loadingHistory.value = true;
    error.value = null;
    try {
      const items = await chatApi.fetchAllThreadMessages(threadId.value);
      messages.value = items.flatMap(historyToDisplayItems);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      error.value = `加载历史失败：${msg}`;
    } finally {
      loadingHistory.value = false;
    }
  }

  function startNewThread(): void {
    abortStreaming();
    const id = crypto.randomUUID();
    persistThreadId(id);
    messages.value = [];
    error.value = null;
  }

  function ensureThreadForUser(userId: string): void {
    const lastUserId = sessionStorage.getItem(LAST_USER_STORAGE_KEY);
    if (lastUserId !== userId) {
      startNewThread();
      sessionStorage.setItem(LAST_USER_STORAGE_KEY, userId);
    }
  }

  function resetOnLogout(): void {
    abortStreaming();
    messages.value = [];
    error.value = null;
    sessionStorage.removeItem(THREAD_STORAGE_KEY);
    sessionStorage.removeItem(LAST_USER_STORAGE_KEY);
    threadId.value = crypto.randomUUID();
  }

  async function copyThreadId(): Promise<void> {
    await navigator.clipboard.writeText(threadId.value);
  }

  function beginAssistantMessage(): string {
    const id = crypto.randomUUID();
    messages.value.push({
      id,
      role: "ai",
      content: "",
      streaming: true,
    });
    streamingMessageId = id;
    streamingSegments = {
      order: [],
      segments: new Map(),
      plain: "",
    };
    return id;
  }

  function updateStreamingAssistant(): void {
    if (!streamingMessageId || !streamingSegments) {
      return;
    }
    const msg = messages.value.find((item) => item.id === streamingMessageId);
    if (msg) {
      msg.content = segmentsToText(streamingSegments);
    }
  }

  function applySseEvent(event: SseEvent): boolean {
    if (event.type === "token" && typeof event.content === "string") {
      if (!streamingMessageId) {
        beginAssistantMessage();
      }
      const state = streamingSegments!;
      if (typeof event.segment_id === "string") {
        const existing = state.segments.get(event.segment_id) ?? "";
        state.segments.set(event.segment_id, existing + event.content);
        if (!state.order.includes(event.segment_id)) {
          state.order.push(event.segment_id);
        }
      } else {
        state.plain += event.content;
      }
      updateStreamingAssistant();
      return false;
    }

    if (event.type === "retract" && typeof event.segment_id === "string") {
      const state = streamingSegments;
      if (state) {
        state.segments.delete(event.segment_id);
        state.order = state.order.filter((id) => id !== event.segment_id);
        updateStreamingAssistant();
      }
      return false;
    }

    if (
      event.type === "replace" &&
      typeof event.segment_id === "string" &&
      typeof event.content === "string"
    ) {
      const state = streamingSegments;
      if (state) {
        state.segments.set(event.segment_id, event.content);
        if (!state.order.includes(event.segment_id)) {
          state.order.push(event.segment_id);
        }
        updateStreamingAssistant();
      }
      return false;
    }

    if (event.type === "client_actions") {
      handleClientActions(event.client_actions);
      return false;
    }

    if (event.type === "done") {
      return true;
    }

    if (event.type === "error") {
      error.value =
        typeof event.reason === "string" ? event.reason : "对话流发生错误";
      return true;
    }

    return false;
  }

  async function consumeSseResponse(response: Response): Promise<void> {
    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error("响应体不可读");
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";

      for (const block of parts) {
        for (const line of block.split("\n")) {
          if (!line.startsWith("data: ")) {
            continue;
          }
          let event: SseEvent;
          try {
            event = JSON.parse(line.slice(6)) as SseEvent;
          } catch {
            console.warn("invalid SSE JSON", line);
            continue;
          }
          if (applySseEvent(event)) {
            return;
          }
        }
      }
    }
  }

  async function sendMessage(text: string): Promise<void> {
    const trimmed = text.trim();
    if (!trimmed || sending.value) {
      return;
    }

    abortStreaming();
    error.value = null;
    messages.value.push({
      id: crypto.randomUUID(),
      role: "human",
      content: trimmed,
    });

    sending.value = true;
    streamAbort = new AbortController();

    try {
      const response = await chatApi.sendChatStream({
        threadId: threadId.value,
        message: trimmed,
        signal: streamAbort.signal,
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`HTTP ${response.status}: ${detail}`);
      }

      const contentType = response.headers.get("content-type") ?? "";
      if (contentType.includes("text/event-stream")) {
        await consumeSseResponse(response);
      } else {
        const data = chatApi.parseChatJsonResponse(await response.json());
        if (data.text) {
          messages.value.push({
            id: crypto.randomUUID(),
            role: "ai",
            content: data.text,
          });
        }
        if (data.client_actions) {
          handleClientActions(data.client_actions);
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      const msg = err instanceof Error ? err.message : String(err);
      error.value = `发送失败：${msg}`;
      console.error(err);
    } finally {
      if (streamingMessageId) {
        const msg = messages.value.find((item) => item.id === streamingMessageId);
        if (msg) {
          msg.streaming = false;
        }
      }
      streamingMessageId = null;
      streamingSegments = null;
      streamAbort = null;
      sending.value = false;
    }
  }

  watch(drawerOpen, (open) => {
    if (open) {
      void loadHistory();
    } else {
      abortStreaming();
    }
  });

  function clearError(): void {
    error.value = null;
  }

  return {
    drawerOpen,
    threadId,
    messages,
    loadingHistory,
    sending,
    error,
    openDrawer,
    closeDrawer,
    toggleDrawer,
    loadHistory,
    startNewThread,
    ensureThreadForUser,
    resetOnLogout,
    copyThreadId,
    sendMessage,
    confirmJumpPage,
    cancelJumpPage,
    confirmCreateStudent,
    cancelCreateStudent,
    abortStreaming,
    clearError,
  };
});
