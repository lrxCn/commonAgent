import axios from "axios";
import { defineStore } from "pinia";
import { createDiscreteApi } from "naive-ui";
import { ref, watch } from "vue";

import * as chatApi from "@/api/chat";
import * as studentsApi from "@/api/students";
import { validateCreateStudentAction } from "@/client-actions/create-student";
import {
  DEFAULT_LIST_AFTER_CREATE,
  sanitizeListStudentsArgs,
  validateListStudentsAction,
} from "@/client-actions/list-students";
import {
  isPageAllowedForUser,
  PAGE_SLUG_LABELS,
  parsePageSlug,
  resolveJumpPageTarget,
} from "@/client-actions/page-registry";
import { useAuthStore } from "@/stores/auth";
import { useStudentsStore } from "@/stores/students";
import { randomId } from "@/utils/randomId";
import type {
  ApiErrorBody,
  ChatDisplayMessage,
  ClientAction,
  CreateStudentFormStatus,
  HistoryMessageItem,
  JumpPageArgs,
  JumpPagePrompt,
  JumpPagePromptStatus,
  ListStudentsMessage,
  PageSlug,
  StudentCreateRequest,
  StudentListParams,
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
    id = randomId();
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
    id: randomId(),
    role: "ai",
    content: "",
    jumpPagePrompt,
  };
}

function buildCreateStudentFormMessage(
  action: ClientAction,
  initialStatus: CreateStudentFormStatus,
  prefillOverride?: Partial<StudentCreateRequest>,
): ChatDisplayMessage | null {
  const validation = validateCreateStudentAction(action);
  if (!validation.ok) {
    return null;
  }

  return {
    id: randomId(),
    role: "ai",
    content: "",
    createStudentForm: {
      prefill: prefillOverride ?? validation.args,
      status: initialStatus,
    },
  };
}

function buildListStudentsMessage(
  query: StudentListParams,
  initialStatus: ListStudentsMessage["status"],
): ChatDisplayMessage {
  return {
    id: randomId(),
    role: "ai",
    content: "",
    listStudents: {
      query,
      status: initialStatus,
    },
  };
}

function extractApiFieldErrors(error: unknown): {
  message: string;
  fieldErrors: Record<string, string>;
} {
  if (axios.isAxiosError(error) && error.response?.data) {
    const body = error.response.data as ApiErrorBody;
    return {
      message: body.message || "创建员工失败",
      fieldErrors: body.field_errors ?? {},
    };
  }
  if (error instanceof Error) {
    return { message: error.message, fieldErrors: {} };
  }
  return { message: "创建员工失败", fieldErrors: {} };
}

function historyToDisplayItems(item: HistoryMessageItem): ChatDisplayMessage[] {
  if (item.role === "tool" || item.role === "other") {
    return [];
  }

  const items: ChatDisplayMessage[] = [];
  const content = item.content?.trim() ?? "";
  if (content || item.role === "human") {
    items.push({
      id: item.message_id ?? randomId(),
      role: item.role,
      content: item.content,
    });
  }

  if (item.client_actions?.length) {
    for (const action of item.client_actions) {
      if (action.tool === "jumpPage") {
        items.push(buildJumpPagePromptMessage(action, "historical"));
        continue;
      }
      if (action.tool === "createStudent") {
        const formMessage = buildCreateStudentFormMessage(action, "historical");
        if (formMessage) {
          items.push(formMessage);
        }
        continue;
      }
      if (action.tool === "listStudents") {
        const validation = validateListStudentsAction(action);
        if (validation.ok) {
          items.push(buildListStudentsMessage(validation.query, "historical"));
        }
        continue;
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

  function enqueueCreateStudentForm(action: ClientAction): void {
    const validation = validateCreateStudentAction(action);
    if (!validation.ok) {
      message.warning(validation.detail);
      if (import.meta.env.DEV) {
        console.warn("[client_actions] createStudent validation failed", validation.detail, action);
      }
      return;
    }

    const formMessage = buildCreateStudentFormMessage(action, "editable");
    if (!formMessage) {
      return;
    }
    messages.value.push(formMessage);
    if (import.meta.env.DEV) {
      console.info("[client_actions] createStudent form enqueued", {
        action,
        prefill: validation.args,
      });
    }
  }

  async function submitCreateStudentForm(
    messageId: string,
    payload: StudentCreateRequest,
  ): Promise<void> {
    const entry = messages.value.find((item) => item.id === messageId);
    const form = entry?.createStudentForm;
    if (!entry || !form || (form.status !== "editable" && form.status !== "error")) {
      return;
    }

    if (!payload.student_no.trim() || !payload.name.trim()) {
      message.warning("请填写工号和姓名");
      return;
    }

    form.status = "submitting";
    form.errorDetail = undefined;
    form.fieldErrors = undefined;

    try {
      const created = await studentsApi.createStudent({
        student_no: payload.student_no.trim(),
        name: payload.name.trim(),
        class_name: payload.class_name?.trim() || null,
        status: payload.status ?? "active",
      });
      form.status = "success";
      form.createdStudent = created;
      useStudentsStore().markListChanged();
      appendListStudents(DEFAULT_LIST_AFTER_CREATE);
      if (import.meta.env.DEV) {
        console.info("[client_actions] createStudent succeeded", created);
      }
    } catch (err) {
      const { message: detail, fieldErrors } = extractApiFieldErrors(err);
      form.status = "error";
      form.errorDetail = detail;
      form.fieldErrors = fieldErrors;
      console.error("[client_actions] createStudent failed", err);
    }
  }

  function cancelCreateStudentForm(messageId: string): void {
    const entry = messages.value.find((item) => item.id === messageId);
    const form = entry?.createStudentForm;
    if (!entry || !form || (form.status !== "editable" && form.status !== "error")) {
      return;
    }
    form.status = "cancelled";
    if (import.meta.env.DEV) {
      console.log("[client_actions] createStudent cancelled");
    }
  }

  /** Front-only chain after create success; does not call Agent. */
  function appendListStudents(query: StudentListParams = DEFAULT_LIST_AFTER_CREATE): void {
    const listMessage = buildListStudentsMessage(query, "loading");
    messages.value.push(listMessage);
    void refreshListStudents(listMessage.id, query);
    if (import.meta.env.DEV) {
      console.info("[client_actions] listStudents appended after create", { query });
    }
  }

  function enqueueListStudents(action: ClientAction): void {
    const validation = validateListStudentsAction(action);
    if (!validation.ok) {
      message.warning(validation.detail);
      if (import.meta.env.DEV) {
        console.warn("[client_actions] listStudents validation failed", validation.detail, action);
      }
      return;
    }

    const listMessage = buildListStudentsMessage(validation.query, "loading");
    messages.value.push(listMessage);
    void refreshListStudents(listMessage.id, validation.query);
    if (import.meta.env.DEV) {
      console.info("[client_actions] listStudents enqueued", {
        action,
        query: validation.query,
      });
    }
  }

  async function refreshListStudents(
    messageId: string,
    rawQuery: StudentListParams,
  ): Promise<void> {
    const entry = messages.value.find((item) => item.id === messageId);
    const list = entry?.listStudents;
    if (!entry || !list || list.status === "historical") {
      return;
    }

    const query = sanitizeListStudentsArgs(rawQuery as Record<string, unknown>);
    list.query = query;
    list.status = "loading";
    list.errorDetail = undefined;

    try {
      list.data = await studentsApi.fetchStudents(query);
      list.status = "ready";
      if (import.meta.env.DEV) {
        console.info("[client_actions] listStudents ready", {
          messageId,
          total: list.data.total,
        });
      }
    } catch (err) {
      const { message: detail } = extractApiFieldErrors(err);
      list.status = "error";
      list.errorDetail = detail;
      console.error("[client_actions] listStudents fetch failed", err);
    }
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
        enqueueCreateStudentForm(record);
        continue;
      }
      if (record.tool === "listStudents") {
        enqueueListStudents(record);
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
    const id = randomId();
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
    threadId.value = randomId();
  }

  async function copyThreadId(): Promise<void> {
    await navigator.clipboard.writeText(threadId.value);
  }

  function beginAssistantMessage(): string {
    const id = randomId();
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
      id: randomId(),
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
            id: randomId(),
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
    submitCreateStudentForm,
    cancelCreateStudentForm,
    refreshListStudents,
    abortStreaming,
    clearError,
  };
});
