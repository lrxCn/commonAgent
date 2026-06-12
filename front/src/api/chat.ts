import http from "@/api/http";
import type {
  ChatJsonResponse,
  ClientAction,
  HistoryMessagesResponse,
} from "@/types";

export type SendChatOptions = {
  threadId: string;
  message: string;
  signal?: AbortSignal;
};

function readErrorMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const record = payload as Record<string, unknown>;
  const detail = record.detail;
  if (detail && typeof detail === "object") {
    const message = (detail as Record<string, unknown>).message;
    if (typeof message === "string" && message.trim()) {
      return message.trim();
    }
  }
  const message = record.message;
  if (typeof message === "string" && message.trim()) {
    return message.trim();
  }
  return null;
}

/** Stream chat via Back; returns the raw Response for SSE consumption. */
export async function sendChatStream(
  options: SendChatOptions,
): Promise<Response> {
  const response = await fetch("/api/chat", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      thread_id: options.threadId,
      message: options.message,
    }),
    signal: options.signal,
  });
  return response;
}

export async function parseChatErrorResponse(response: Response): Promise<string> {
  const fallback =
    "抱歉，我不支持回答涉及伤害他人、自我伤害、政治敏感话题、违法犯罪或规避执法的问题。如果你正处于危险或紧急情况，请立即联系当地应急服务或可信任的人。";
  const raw = await response.text();
  if (!raw.trim()) {
    return fallback;
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    return readErrorMessage(parsed) ?? fallback;
  } catch {
    return raw.trim();
  }
}

export async function fetchThreadMessages(
  threadId: string,
  params: { cursor?: string; limit?: number } = {},
): Promise<HistoryMessagesResponse> {
  const { data } = await http.get<HistoryMessagesResponse>(
    `/api/threads/${encodeURIComponent(threadId)}/messages`,
    { params },
  );
  return data;
}

export async function fetchAllThreadMessages(
  threadId: string,
): Promise<HistoryMessagesResponse["items"]> {
  const items: HistoryMessagesResponse["items"] = [];
  let cursor: string | undefined;
  for (;;) {
    const page = await fetchThreadMessages(threadId, { cursor, limit: 100 });
    items.push(...page.items);
    if (!page.next_cursor) {
      break;
    }
    cursor = page.next_cursor;
  }
  return items;
}

export function parseChatJsonResponse(payload: unknown): ChatJsonResponse {
  if (!payload || typeof payload !== "object") {
    return { text: null, client_actions: null };
  }
  const record = payload as Record<string, unknown>;
  const text =
    typeof record.text === "string"
      ? record.text
      : record.text == null
        ? null
        : String(record.text);
  const rawActions = record.client_actions;
  let client_actions: ClientAction[] | null = null;
  if (Array.isArray(rawActions)) {
    client_actions = rawActions.filter(
      (item): item is ClientAction =>
        Boolean(item) &&
        typeof item === "object" &&
        typeof (item as ClientAction).tool === "string",
    );
    if (client_actions.length === 0) {
      client_actions = null;
    }
  }
  return { text, client_actions };
}
