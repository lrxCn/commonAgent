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
import { getIceServers } from "@/utils/webrtc";

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
  const onlineUserIds = ref<Set<string>>(new Set());
  const pendingInvitePeer = ref<CallPeer | null>(null);
  const notice = ref<string | null>(null);
  const remoteStream = ref<MediaStream | null>(null);
  const callStartedAt = ref<number | null>(null);

  let signaling: CallSignalingConnection | null = null;
  let peerConnection: RTCPeerConnection | null = null;
  let localStream: MediaStream | null = null;
  const pendingIceCandidates: RTCIceCandidateInit[] = [];
  let suppressEndedNotice = false;

  const isOutgoing = computed(() => phase.value === "outgoing");
  const isInCall = computed(() => phase.value === "in_call");
  const hasIncoming = computed(
    () => phase.value === "incoming" && incomingCall.value !== null,
  );

  function clearNotice(): void {
    notice.value = null;
  }

  function sortPeersForDisplay(list: CallPeer[]): CallPeer[] {
    return [...list].sort((a, b) => {
      const aOnline = onlineUserIds.value.has(a.user_id);
      const bOnline = onlineUserIds.value.has(b.user_id);
      if (aOnline !== bOnline) {
        return aOnline ? -1 : 1;
      }
      return a.username.localeCompare(b.username);
    });
  }

  function syncPeersOnlineFlags(): void {
    const updated = peers.value.map((peer) => ({
      ...peer,
      online: onlineUserIds.value.has(peer.user_id),
    }));
    peers.value = sortPeersForDisplay(updated);
  }

  function applyOnlineSnapshot(userIds: string[]): void {
    onlineUserIds.value = new Set(userIds);
    syncPeersOnlineFlags();
  }

  function setPeerOnline(userId: string, online: boolean): void {
    const next = new Set(onlineUserIds.value);
    if (online) {
      next.add(userId);
    } else {
      next.delete(userId);
    }
    onlineUserIds.value = next;
    syncPeersOnlineFlags();
  }

  function isPeerOnline(userId: string): boolean {
    return onlineUserIds.value.has(userId);
  }

  function setNotice(text: string): void {
    notice.value = text;
  }

  function cleanupMedia(): void {
    if (peerConnection) {
      peerConnection.onicecandidate = null;
      peerConnection.ontrack = null;
      peerConnection.close();
      peerConnection = null;
    }
    if (localStream) {
      for (const track of localStream.getTracks()) {
        track.stop();
      }
      localStream = null;
    }
    remoteStream.value = null;
    pendingIceCandidates.length = 0;
    callStartedAt.value = null;
  }

  function resetCallState(): void {
    cleanupMedia();
    phase.value = "idle";
    activeCall.value = null;
    incomingCall.value = null;
    pendingInvitePeer.value = null;
  }

  function markInCall(): void {
    phase.value = "in_call";
    if (callStartedAt.value === null) {
      callStartedAt.value = Date.now();
    }
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

  async function ensureLocalAudio(): Promise<MediaStream> {
    if (localStream) {
      return localStream;
    }
    localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    return localStream;
  }

  function ensurePeerConnection(callId: string): RTCPeerConnection {
    if (peerConnection) {
      return peerConnection;
    }
    const pc = new RTCPeerConnection({ iceServers: getIceServers() });
    pc.onicecandidate = (event) => {
      if (event.candidate) {
        sendMessage({
          type: "rtc.ice",
          call_id: callId,
          candidate: event.candidate.toJSON(),
        });
      }
    };
    pc.ontrack = (event) => {
      const stream =
        event.streams[0] ?? new MediaStream([event.track]);
      remoteStream.value = stream;
    };
    peerConnection = pc;
    return pc;
  }

  function addLocalTracks(pc: RTCPeerConnection): void {
    if (!localStream) {
      return;
    }
    for (const track of localStream.getTracks()) {
      pc.addTrack(track, localStream);
    }
  }

  async function flushPendingIce(pc: RTCPeerConnection): Promise<void> {
    while (pendingIceCandidates.length > 0) {
      const candidate = pendingIceCandidates.shift();
      if (candidate) {
        await pc.addIceCandidate(candidate);
      }
    }
  }

  async function handleRtcOffer(callId: string, sdp: string): Promise<void> {
    try {
      const pc = ensurePeerConnection(callId);
      addLocalTracks(pc);
      await pc.setRemoteDescription({ type: "offer", sdp });
      await flushPendingIce(pc);
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      if (!answer.sdp) {
        throw new Error("无法创建 answer SDP");
      }
      sendMessage({ type: "rtc.answer", call_id: callId, sdp: answer.sdp });
    } catch {
      setNotice("建立媒体连接失败");
      hangup();
    }
  }

  async function handleRtcAnswer(callId: string, sdp: string): Promise<void> {
    try {
      const pc = ensurePeerConnection(callId);
      await pc.setRemoteDescription({ type: "answer", sdp });
      await flushPendingIce(pc);
    } catch {
      setNotice("建立媒体连接失败");
      hangup();
    }
  }

  async function handleRtcIce(
    _callId: string,
    candidate: Record<string, unknown>,
  ): Promise<void> {
    const init = candidate as RTCIceCandidateInit;
    const pc = peerConnection;
    if (!pc || !pc.remoteDescription) {
      pendingIceCandidates.push(init);
      return;
    }
    try {
      await pc.addIceCandidate(init);
    } catch {
      // ignore late/duplicate ICE in demo
    }
  }

  async function startCallerWebRtc(callId: string): Promise<void> {
    try {
      await ensureLocalAudio();
      const pc = ensurePeerConnection(callId);
      addLocalTracks(pc);
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      if (!offer.sdp) {
        throw new Error("无法创建 offer SDP");
      }
      sendMessage({ type: "rtc.offer", call_id: callId, sdp: offer.sdp });
    } catch {
      setNotice("无法访问麦克风或建立通话");
      hangup();
    }
  }

  async function onCallAccepted(message: { call_id: string }): Promise<void> {
    if (activeCall.value) {
      activeCall.value = {
        ...activeCall.value,
        callId: message.call_id,
      };
      markInCall();
      if (activeCall.value.role === "caller") {
        await startCallerWebRtc(message.call_id);
      }
      return;
    }
    if (incomingCall.value) {
      activeCall.value = {
        callId: message.call_id,
        peerUserId: incomingCall.value.fromUserId,
        peerDisplayName: incomingCall.value.fromDisplayName,
        role: "callee",
      };
      incomingCall.value = null;
      markInCall();
    }
  }

  function handleServerMessage(message: ServerCallMessage): void {
    switch (message.type) {
      case "connected":
        return;

      case "presence.snapshot":
        applyOnlineSnapshot(message.online_user_ids);
        return;

      case "presence.online":
        setPeerOnline(message.user_id, true);
        return;

      case "presence.offline":
        setPeerOnline(message.user_id, false);
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
        void onCallAccepted(message);
        return;

      case "call.rejected":
        setNotice("对方已拒接");
        resetCallState();
        return;

      case "call.canceled":
        if (phase.value === "incoming" || incomingCall.value) {
          setNotice("已取消呼叫");
        }
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
        if (!suppressEndedNotice) {
          setNotice(endedMessage(message.reason));
        }
        suppressEndedNotice = false;
        resetCallState();
        return;

      case "session.replaced":
        setNotice("通话连接已在其他标签页打开，当前页已断开");
        resetCallState();
        return;

      case "error":
        setNotice(message.message || message.code);
        return;

      case "rtc.offer":
        void handleRtcOffer(message.call_id, message.sdp);
        return;

      case "rtc.answer":
        void handleRtcAnswer(message.call_id, message.sdp);
        return;

      case "rtc.ice":
        void handleRtcIce(message.call_id, message.candidate);
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
      return "对方已挂断";
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
      applyOnlineSnapshot(
        data.items.filter((p) => p.online).map((p) => p.user_id),
      );
    } finally {
      peersLoading.value = false;
    }
  }

  function connectSignaling(): void {
    ensureSignaling().connect();
  }

  function disconnectSignaling(): void {
    suppressEndedNotice = true;
    const callId = activeCall.value?.callId;
    if (callId && phase.value === "in_call") {
      try {
        sendMessage({ type: "call.hangup", call_id: callId });
      } catch {
        // WS may already be closed during logout
      }
    }
    signaling?.disconnect();
    wsConnected.value = false;
    onlineUserIds.value = new Set();
    resetCallState();
    suppressEndedNotice = false;
  }

  function invitePeer(peer: CallPeer): void {
    if (phase.value !== "idle") {
      throw new Error("当前有进行中的呼叫");
    }
    if (!isPeerOnline(peer.user_id)) {
      throw new Error("对方当前不在线");
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
    suppressEndedNotice = true;
    resetCallState();
    suppressEndedNotice = false;
  }

  function rejectIncoming(): void {
    const inc = incomingCall.value;
    if (!inc) {
      return;
    }
    try {
      sendMessage({ type: "call.reject", call_id: inc.callId });
    } catch {
      // best effort
    }
    incomingCall.value = null;
    phase.value = "idle";
  }

  async function acceptIncoming(): Promise<void> {
    const inc = incomingCall.value;
    if (!inc) {
      throw new Error("没有待接听的来电");
    }
    try {
      await ensureLocalAudio();
      sendMessage({ type: "call.accept", call_id: inc.callId });
    } catch (error) {
      cleanupMedia();
      incomingCall.value = null;
      phase.value = "idle";
      if (error instanceof DOMException && error.name === "NotAllowedError") {
        throw new Error("需要麦克风权限才能接听");
      }
      throw error instanceof Error ? error : new Error("接听失败");
    }
  }

  function hangup(): void {
    const callId = activeCall.value?.callId;
    if (callId) {
      try {
        sendMessage({ type: "call.hangup", call_id: callId });
      } catch {
        // ignore if WS gone
      }
    }
    suppressEndedNotice = true;
    resetCallState();
    suppressEndedNotice = false;
  }

  return {
    phase,
    peers,
    peersLoading,
    activeCall,
    incomingCall,
    wsConnected,
    onlineUserIds,
    isPeerOnline,
    notice,
    remoteStream,
    callStartedAt,
    isOutgoing,
    isInCall,
    hasIncoming,
    clearNotice,
    loadPeers,
    connectSignaling,
    disconnectSignaling,
    invitePeer,
    cancelOutgoing,
    rejectIncoming,
    acceptIncoming,
    hangup,
    resetCallState,
  };
});
