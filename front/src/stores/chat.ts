import { defineStore } from "pinia";
import { createDiscreteApi } from "naive-ui";
import { ref, watch } from "vue";

import * as chatApi from "@/api/chat";
import {
  isPageAllowedForUser,
  parsePageSlug,
  resolveJumpPageTarget,
} from "@/client-actions/page-registry";
import { useAuthStore } from "@/stores/auth";
import type { ChatDisplayMessage, ClientAction, HistoryMessageItem, JumpPageArgs } from "@/types";

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

function historyToDisplay(item: HistoryMessageItem): ChatDisplayMessage | null {
  if (item.role === "tool" || item.role === "other") {
    return null;
  }
  return {
    id: item.message_id ?? crypto.randomUUID(),
    role: item.role,
    content: item.content,
  };
}

function segmentsToText(state: StreamingSegments): string {
  if (state.order.length > 0) {
    return state.order.map((id) => state.segments.get(id) ?? "").join("");
  }
  return state.plain;
}

async function executeJumpPage(action: ClientAction): Promise<void> {
  const args = action.args as JumpPageArgs;
  const rawPage = typeof args.page === "string" ? args.page : "";
  const slug = parsePageSlug(rawPage);
  if (!slug) {
    message.warning("未知页面，无法跳转");
    return;
  }

  const auth = useAuthStore();
  if (!auth.isAuthenticated) {
    message.warning("请先登录后再跳转页面");
    return;
  }

  if (!isPageAllowedForUser(slug, auth.isAdmin)) {
    message.warning("当前账号无权访问该页面");
    return;
  }

  const target = resolveJumpPageTarget(rawPage);
  if (!target) {
    message.warning("未知页面，无法跳转");
    return;
  }

  if (action.requires_approval) {
    const prompt = `跳转到「${slug}」？\n参数：${JSON.stringify(action.args ?? {}, null, 2)}`;
    if (!window.confirm(prompt)) {
      if (import.meta.env.DEV) {
        console.log("[client_actions] skipped (user declined)", action);
      }
      return;
    }
  }

  const { default: router } = await import("@/router");
  try {
    await router.push(target);
    if (import.meta.env.DEV) {
      console.info("[client_actions] jumpPage navigated", { page: slug, target });
    }
  } catch (err) {
    console.error("[client_actions] jumpPage navigation failed", err);
    message.warning("页面跳转失败");
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
      void executeJumpPage(record);
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
      messages.value = items
        .map(historyToDisplay)
        .filter((item): item is ChatDisplayMessage => item !== null);
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
    abortStreaming,
    clearError,
  };
});
