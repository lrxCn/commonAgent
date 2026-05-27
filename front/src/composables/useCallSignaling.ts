import type { ClientCallMessage, ServerCallMessage } from "@/types/call";
import { isServerCallMessage } from "@/types/call";

const DEFAULT_WS_PATH = "/api/calls/ws";
const MAX_RECONNECT_MS = 30_000;
const INITIAL_RECONNECT_MS = 1_000;

export function buildCallWsUrl(): string {
  const path = import.meta.env.VITE_CALL_WS_PATH ?? DEFAULT_WS_PATH;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${normalizedPath}`;
}

export interface CallSignalingHandlers {
  onMessage: (message: ServerCallMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

export interface CallSignalingConnection {
  connect: () => void;
  disconnect: () => void;
  send: (message: ClientCallMessage) => void;
  readonly isConnected: () => boolean;
}

/** WebSocket client with exponential backoff reconnect (no call recovery). */
export function createCallSignaling(
  handlers: CallSignalingHandlers,
): CallSignalingConnection {
  let socket: WebSocket | null = null;
  let intentionalClose = false;
  let reconnectAttempt = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  function clearReconnectTimer(): void {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  function scheduleReconnect(): void {
    if (intentionalClose) {
      return;
    }
    const delay = Math.min(
      INITIAL_RECONNECT_MS * 2 ** reconnectAttempt,
      MAX_RECONNECT_MS,
    );
    reconnectAttempt += 1;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      openSocket();
    }, delay);
  }

  function openSocket(): void {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const url = buildCallWsUrl();
    const ws = new WebSocket(url);
    socket = ws;

    ws.addEventListener("open", () => {
      reconnectAttempt = 0;
      handlers.onOpen?.();
    });

    ws.addEventListener("message", (event) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(String(event.data));
      } catch {
        return;
      }
      if (!isServerCallMessage(parsed)) {
        return;
      }
      handlers.onMessage(parsed);
    });

    ws.addEventListener("close", () => {
      if (socket === ws) {
        socket = null;
      }
      handlers.onClose?.();
      if (!intentionalClose) {
        scheduleReconnect();
      }
    });

    ws.addEventListener("error", () => {
      ws.close();
    });
  }

  function connect(): void {
    intentionalClose = false;
    reconnectAttempt = 0;
    clearReconnectTimer();
    openSocket();
  }

  function disconnect(): void {
    intentionalClose = true;
    clearReconnectTimer();
    if (socket) {
      socket.close();
      socket = null;
    }
  }

  function send(message: ClientCallMessage): void {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      throw new Error("信令未连接");
    }
    socket.send(JSON.stringify(message));
  }

  function isConnected(): boolean {
    return socket?.readyState === WebSocket.OPEN;
  }

  return { connect, disconnect, send, isConnected };
}
