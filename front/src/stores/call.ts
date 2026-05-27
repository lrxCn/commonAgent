import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { fetchPeers } from "@/api/calls";
import {
  createCallSignaling,
  type CallSignalingConnection,
} from "@/composables/useCallSignaling";
import type {
  ActiveCall,
  CallPeer,
  CallPhase,
  ClientCallMessage,
  IncomingCall,
  ServerCallMessage,
} from "@/types/call";

function peerLabel(peer: CallPeer): string {
  return peer.display_name?.trim() || peer.username;
}

export const useCallStore = defineStore("call", () => {
  const phase = ref<CallPhase>("idle");
  const peers = ref<CallPeer[]>([]);
  const peersLoading = ref(false);
  const activeCall = ref<ActiveCall | null>(null);
  const incomingCall = ref<IncomingCall | null>(null);
  const wsConnected = ref(false);
  const pendingInvitePeer = ref<CallPeer | null>(null);
  const notice = ref<string | null>(null);

  let signaling: CallSignalingConnection | null = null;

  const isOutgoing = computed(() => phase.value === "outgoing");
  const isInCall = computed(() => phase.value === "in_call");

  function clearNotice(): void {
    notice.value = null;
  }

  function setNotice(text: string): void {
    notice.value = text;
  }

  function resetCallState(): void {
    phase.value = "idle";
    activeCall.value = null;
    incomingCall.value = null;
    pendingInvitePeer.value = null;
  }

  function ensureSignaling(): CallSignalingConnection {
    if (!signaling) {
      signaling = createCallSignaling({
        onOpen: () => {
          wsConnected.value = true;
        },
        onClose: () => {
          wsConnected.value = false;
        },
        onMessage: handleServerMessage,
      });
    }
    return signaling;
  }

  function sendMessage(message: ClientCallMessage): void {
    const conn = ensureSignaling();
    if (!conn.isConnected()) {
      throw new Error("信令未连接，请稍后重试");
    }
    conn.send(message);
  }

  function handleServerMessage(message: ServerCallMessage): void {
    switch (message.type) {
      case "connected":
        return;

      case "call.ringing": {
        const peer = pendingInvitePeer.value;
        activeCall.value = {
          callId: message.call_id,
          peerUserId: message.to_user_id,
          peerDisplayName: peer ? peerLabel(peer) : message.to_user_id,
          role: "caller",
        };
        phase.value = "outgoing";
        return;
      }

      case "call.incoming":
        incomingCall.value = {
          callId: message.call_id,
          fromUserId: message.from_user_id,
          fromDisplayName: message.from_display_name,
        };
        if (phase.value === "idle") {
          phase.value = "incoming";
        }
        return;

      case "call.accepted":
        if (activeCall.value) {
          phase.value = "in_call";
        } else if (incomingCall.value) {
          activeCall.value = {
            callId: message.call_id,
            peerUserId: incomingCall.value.fromUserId,
            peerDisplayName: incomingCall.value.fromDisplayName,
            role: "callee",
          };
          incomingCall.value = null;
          phase.value = "in_call";
        }
        return;

      case "call.rejected":
        setNotice("对方已拒接");
        resetCallState();
        return;

      case "call.canceled":
        setNotice("呼叫已取消");
        resetCallState();
        return;

      case "call.failed":
        setNotice(failedMessage(message.code));
        resetCallState();
        return;

      case "call.busy":
        setNotice("对方忙线中");
        resetCallState();
        return;

      case "call.ended":
        setNotice(endedMessage(message.reason));
        resetCallState();
        return;

      case "session.replaced":
        setNotice("通话连接已在其他标签页打开，当前页已断开");
        resetCallState();
        return;

      case "error":
        setNotice(message.message || message.code);
        return;

      default:
        return;
    }
  }

  function failedMessage(code: string): string {
    if (code === "callee_offline") {
      return "对方不在线";
    }
    if (code === "invalid_state") {
      return "呼叫状态无效";
    }
    return `呼叫失败（${code}）`;
  }

  function endedMessage(reason: string): string {
    if (reason === "hangup") {
      return "通话已结束";
    }
    if (reason === "peer_disconnected") {
      return "对方已断开连接";
    }
    return "通话已结束";
  }

  async function loadPeers(): Promise<void> {
    peersLoading.value = true;
    try {
      const data = await fetchPeers();
      peers.value = data.items;
    } finally {
      peersLoading.value = false;
    }
  }

  function connectSignaling(): void {
    ensureSignaling().connect();
  }

  function disconnectSignaling(): void {
    signaling?.disconnect();
    wsConnected.value = false;
  }

  function invitePeer(peer: CallPeer): void {
    if (phase.value !== "idle") {
      throw new Error("当前有进行中的呼叫");
    }
    pendingInvitePeer.value = peer;
    phase.value = "outgoing";
    activeCall.value = {
      callId: "",
      peerUserId: peer.user_id,
      peerDisplayName: peerLabel(peer),
      role: "caller",
    };
    try {
      sendMessage({ type: "call.invite", to_user_id: peer.user_id });
    } catch (error) {
      resetCallState();
      throw error;
    }
  }

  function cancelOutgoing(): void {
    const callId = activeCall.value?.callId;
    if (callId) {
      sendMessage({ type: "call.cancel", call_id: callId });
    }
    resetCallState();
  }

  function hangup(): void {
    const callId = activeCall.value?.callId;
    if (callId) {
      sendMessage({ type: "call.hangup", call_id: callId });
    }
    resetCallState();
  }

  return {
    phase,
    peers,
    peersLoading,
    activeCall,
    incomingCall,
    wsConnected,
    notice,
    isOutgoing,
    isInCall,
    clearNotice,
    loadPeers,
    connectSignaling,
    disconnectSignaling,
    invitePeer,
    cancelOutgoing,
    hangup,
    resetCallState,
  };
});
