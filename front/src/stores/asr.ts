import { defineStore } from "pinia";
import { computed, ref, watch, type WatchStopHandle } from "vue";

import {
  startAsrCapture,
  type AsrCaptureHandle,
} from "@/composables/useAsrCapture";
import { useAuthStore } from "@/stores/auth";
import { useCallStore } from "@/stores/call";
import type {
  AsrClientMessage,
  AsrServerMessage,
  AsrTrack,
  AsrTranscriptLine,
} from "@/types/asr";
import { isAsrServerMessage } from "@/types/asr";

const DEFAULT_WS_PATH = "/api/asr/ws";

function buildAsrWsUrl(): string {
  const path = DEFAULT_WS_PATH;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

function trackRoleLabel(track: AsrTrack, localLabel: string, remoteLabel: string): string {
  return track === "local" ? `本地 · ${localLabel}` : `对方 · ${remoteLabel}`;
}

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

export const useAsrStore = defineStore("asr", () => {
  const wsConnected = ref(false);
  const active = ref(false);
  const error = ref<string | null>(null);
  const partials = ref<Record<AsrTrack, string>>({ local: "", remote: "" });
  const finalLines = ref<AsrTranscriptLine[]>([]);

  let socket: WebSocket | null = null;
  let callBindingStop: WatchStopHandle | null = null;
  let localCapture: AsrCaptureHandle | null = null;
  let remoteCapture: AsrCaptureHandle | null = null;
  let remoteStreamStop: WatchStopHandle | null = null;
  let seq = 0;

  let sessionCallId = "";
  let sessionLocalLabel = "";
  let sessionRemoteLabel = "";
  let sessionStartedAt = 0;

  const hasSubtitles = computed(
    () =>
      active.value ||
      partials.value.local.length > 0 ||
      partials.value.remote.length > 0 ||
      finalLines.value.length > 0,
  );

  const localFinalLines = computed(() =>
    finalLines.value.filter((line) => line.track === "local"),
  );

  const remoteFinalLines = computed(() =>
    finalLines.value.filter((line) => line.track === "remote"),
  );

  function resetTranscriptState(): void {
    partials.value = { local: "", remote: "" };
    finalLines.value = [];
    error.value = null;
    seq = 0;
  }

  function sendJson(message: AsrClientMessage): void {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }
    socket.send(JSON.stringify(message));
  }

  function sendAudio(track: AsrTrack, buffer: ArrayBuffer): void {
    if (!socket || socket.readyState !== WebSocket.OPEN || !active.value) {
      return;
    }
    sendJson({ type: "asr.track", track });
    socket.send(buffer);
  }

  function handleServerMessage(message: AsrServerMessage): void {
    switch (message.type) {
      case "connected":
        return;

      case "asr.partial":
        partials.value = {
          ...partials.value,
          [message.track]: message.text,
        };
        return;

      case "asr.final": {
        partials.value = {
          ...partials.value,
          [message.track]: "",
        };
        seq += 1;
        finalLines.value.push({
          track: message.track,
          text: message.text,
          startTime:
            typeof message.start_time === "number" ? message.start_time : undefined,
          endTime:
            typeof message.end_time === "number" ? message.end_time : undefined,
          seq,
        });
        return;
      }

      case "asr.error":
        error.value = message.message || message.code;
        return;

      case "asr.ended":
        return;

      default:
        return;
    }
  }

  function openSocket(): void {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const ws = new WebSocket(buildAsrWsUrl());
    socket = ws;

    ws.addEventListener("open", () => {
      wsConnected.value = true;
    });

    ws.addEventListener("message", (event) => {
      if (typeof event.data !== "string") {
        return;
      }
      let parsed: unknown;
      try {
        parsed = JSON.parse(event.data);
      } catch {
        return;
      }
      if (!isAsrServerMessage(parsed)) {
        return;
      }
      handleServerMessage(parsed);
    });

    ws.addEventListener("close", () => {
      if (socket === ws) {
        socket = null;
      }
      wsConnected.value = false;
    });

    ws.addEventListener("error", () => {
      ws.close();
    });
  }

  function disconnect(): void {
    if (socket) {
      socket.close();
      socket = null;
    }
    wsConnected.value = false;
  }

  function stopCaptures(): void {
    localCapture?.stop();
    localCapture = null;
    remoteCapture?.stop();
    remoteCapture = null;
    remoteStreamStop?.();
    remoteStreamStop = null;
  }

  function startLocalCapture(stream: MediaStream): void {
    localCapture?.stop();
    localCapture = startAsrCapture(stream, "local", sendAudio);
  }

  function startRemoteCapture(stream: MediaStream): void {
    remoteCapture?.stop();
    remoteCapture = startAsrCapture(stream, "remote", sendAudio);
  }

  function watchRemoteStream(): void {
    remoteStreamStop?.();
    const callStore = useCallStore();
    remoteStreamStop = watch(
      () => callStore.remoteStream,
      (stream) => {
        if (!active.value || !stream) {
          return;
        }
        startRemoteCapture(stream);
      },
      { immediate: true },
    );
  }

  function dumpTranscriptToConsole(): void {
    if (finalLines.value.length === 0) {
      return;
    }

    const durationMs =
      sessionStartedAt > 0 ? Date.now() - sessionStartedAt : 0;
    const durationLabel = formatDuration(durationMs);
    const callId = sessionCallId || "unknown";

    const sorted = [...finalLines.value].sort((a, b) => {
      if (a.startTime !== undefined && b.startTime !== undefined) {
        return a.startTime - b.startTime;
      }
      return a.seq - b.seq;
    });

    console.group(`[Call Transcript] ${callId} (${durationLabel})`);
    for (const line of sorted) {
      const role = trackRoleLabel(
        line.track,
        sessionLocalLabel,
        sessionRemoteLabel,
      );
      console.log(`[${role}] ${line.text}`);
    }
    console.groupEnd();
  }

  async function stopAll(options: { dump?: boolean } = {}): Promise<void> {
    const shouldDump = options.dump ?? true;
    if (!active.value && !localCapture && !remoteCapture) {
      if (shouldDump) {
        dumpTranscriptToConsole();
      }
      return;
    }

    active.value = false;
    stopCaptures();

    sendJson({ type: "asr.stop", track: "local" });
    sendJson({ type: "asr.stop", track: "remote" });

    if (shouldDump) {
      dumpTranscriptToConsole();
    }

    sessionCallId = "";
    sessionLocalLabel = "";
    sessionRemoteLabel = "";
    sessionStartedAt = 0;
  }

  function startCallTracks(
    callId: string,
    labels: { localLabel: string; remoteLabel: string },
  ): void {
    const callStore = useCallStore();
    resetTranscriptState();
    active.value = true;
    sessionCallId = callId;
    sessionLocalLabel = labels.localLabel;
    sessionRemoteLabel = labels.remoteLabel;
    sessionStartedAt = callStore.callStartedAt ?? Date.now();

    openSocket();

    const startTracks = (): void => {
      sendJson({
        type: "asr.start",
        scene: "call",
        track: "local",
        call_id: callId,
      });
      sendJson({
        type: "asr.start",
        scene: "call",
        track: "remote",
        call_id: callId,
      });

      const localStream = callStore.getLocalStream();
      if (localStream) {
        startLocalCapture(localStream);
      }
      watchRemoteStream();
    };

    if (socket?.readyState === WebSocket.OPEN) {
      startTracks();
      return;
    }

    const ws = socket;
    if (!ws) {
      openSocket();
    }
    const target = socket;
    if (!target) {
      return;
    }

    const onOpen = (): void => {
      target.removeEventListener("open", onOpen);
      if (active.value) {
        startTracks();
      }
    };
    if (target.readyState === WebSocket.OPEN) {
      startTracks();
    } else {
      target.addEventListener("open", onOpen);
    }
  }

  function bindCallLifecycle(): void {
    if (callBindingStop) {
      return;
    }

    const callStore = useCallStore();
    const authStore = useAuthStore();

    callBindingStop = watch(
      () => callStore.isInCall,
      (inCall, wasInCall) => {
        if (inCall && !wasInCall) {
          const call = callStore.activeCall;
          if (!call?.callId) {
            return;
          }
          const localLabel =
            authStore.user?.display_name?.trim() ||
            authStore.user?.username ||
            "我";
          startCallTracks(call.callId, {
            localLabel,
            remoteLabel: call.peerDisplayName,
          });
          return;
        }

        if (!inCall && wasInCall) {
          void stopAll({ dump: true });
          resetTranscriptState();
        }
      },
    );
  }

  function unbindCallLifecycle(): void {
    callBindingStop?.();
    callBindingStop = null;
    void stopAll({ dump: false });
    stopCaptures();
    disconnect();
  }

  return {
    wsConnected,
    active,
    error,
    partials,
    finalLines,
    localFinalLines,
    remoteFinalLines,
    hasSubtitles,
    bindCallLifecycle,
    unbindCallLifecycle,
    startCallTracks,
    stopAll,
    disconnect,
  };
});
