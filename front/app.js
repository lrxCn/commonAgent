/**
 * Front stub: thread_id in sessionStorage, chat via Back, SSE display, client_actions → console.
 */

const THREAD_STORAGE_KEY = "common_agent_thread_id";
const DEFAULT_BACK_URL = "http://127.0.0.1:8080";

const backUrlInput = document.getElementById("back-url");
const threadIdEl = document.getElementById("thread-id");
const logEl = document.getElementById("log");
const formEl = document.getElementById("chat-form");
const messageEl = document.getElementById("message");
const sendBtn = document.getElementById("send");
const newThreadBtn = document.getElementById("new-thread");

function getBackBaseUrl() {
  const raw = backUrlInput.value.trim() || DEFAULT_BACK_URL;
  return raw.replace(/\/$/, "");
}

function getThreadId() {
  let id = sessionStorage.getItem(THREAD_STORAGE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(THREAD_STORAGE_KEY, id);
  }
  return id;
}

function setThreadId(id) {
  sessionStorage.setItem(THREAD_STORAGE_KEY, id);
  threadIdEl.textContent = id;
}

function startNewThread() {
  const id = crypto.randomUUID();
  setThreadId(id);
  logEl.innerHTML = "";
  appendSystem("已新开 thread_id；改权限或上传文档后请使用新 thread。");
}

function appendEntry(role, text, extraClass = "") {
  const article = document.createElement("article");
  article.className = `entry entry-${role} ${extraClass}`.trim();
  const label = document.createElement("strong");
  label.textContent = role === "human" ? "你" : role === "ai" ? "助手" : "系统";
  const body = document.createElement("p");
  body.textContent = text;
  article.append(label, body);
  logEl.append(article);
  logEl.scrollTop = logEl.scrollHeight;
  return body;
}

function appendSystem(text) {
  appendEntry("system", text);
}

function appendHuman(text) {
  appendEntry("human", text);
}

function appendAssistantStreaming() {
  const article = document.createElement("article");
  article.className = "entry entry-ai";
  const label = document.createElement("strong");
  label.textContent = "助手";
  const body = document.createElement("p");
  body.textContent = "";
  article.append(label, body);
  logEl.append(article);
  logEl.scrollTop = logEl.scrollHeight;
  return body;
}

/**
 * @param {unknown} actions
 */
function handleClientActions(actions) {
  if (!Array.isArray(actions)) {
    console.warn("[client_actions] expected array, got", actions);
    return;
  }
  for (const action of actions) {
    if (!action || typeof action !== "object") {
      continue;
    }
    const tool = action.tool ?? "(unknown)";
    const needsApproval = Boolean(action.requires_approval);
    const prompt = `执行工具「${tool}」？\n参数：${JSON.stringify(action.args ?? {}, null, 2)}`;
    if (needsApproval && !window.confirm(prompt)) {
      console.log("[client_actions] skipped (user declined)", action);
      continue;
    }
    console.log("[client_actions]", action);
  }
}

/**
 * @param {{ text?: string | null; client_actions?: unknown }} payload
 */
function handleJsonChatPayload(payload) {
  if (payload.text) {
    appendEntry("ai", payload.text);
  }
  if (payload.client_actions) {
    handleClientActions(payload.client_actions);
  }
}

/**
 * @param {Response} response
 */
async function consumeSseResponse(response) {
  const assistantBody = appendAssistantStreaming();
  const reader = response.body.getReader();
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
        let event;
        try {
          event = JSON.parse(line.slice(6));
        } catch {
          console.warn("invalid SSE JSON", line);
          continue;
        }
        if (event.type === "token" && typeof event.content === "string") {
          assistantBody.textContent += event.content;
          logEl.scrollTop = logEl.scrollHeight;
        }
        if (event.type === "done") {
          return;
        }
      }
    }
  }
}

async function sendChat(message) {
  const backUrl = getBackBaseUrl();
  const threadId = getThreadId();

  appendHuman(message);
  sendBtn.disabled = true;

  try {
    const response = await fetch(`${backUrl}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thread_id: threadId, message }),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`HTTP ${response.status}: ${detail}`);
    }

    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("text/event-stream")) {
      await consumeSseResponse(response);
      return;
    }

    const data = await response.json();
    handleJsonChatPayload(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    appendSystem(`请求失败：${msg}`);
    console.error(err);
  } finally {
    sendBtn.disabled = false;
  }
}

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = messageEl.value.trim();
  if (!text) {
    return;
  }
  messageEl.value = "";
  void sendChat(text);
});

newThreadBtn.addEventListener("click", () => {
  startNewThread();
});

setThreadId(getThreadId());
appendSystem("Front 占位已就绪。打开 DevTools Console 查看 client_actions。");
