/** Call signaling phase (WebRTC media in task 113). */
export type CallPhase = "idle" | "outgoing" | "incoming" | "in_call";

export interface CallPeer {
  user_id: string;
  username: string;
  display_name: string;
  /** Whether the peer has an active signaling WebSocket (from REST or presence events). */
  online?: boolean;
}

export interface ActiveCall {
  callId: string;
  peerUserId: string;
  peerDisplayName: string;
  role: "caller" | "callee";
}

export interface IncomingCall {
  callId: string;
  fromUserId: string;
  fromDisplayName: string;
}

export interface CallPeersResponse {
  items: CallPeer[];
}

export interface CallTranscriptLinePayload {
  track: "local" | "remote";
  role_label: string;
  text: string;
  seq: number;
  start_time?: number;
  end_time?: number;
}

export interface CallTranscriptPayload {
  call_id?: string;
  peer_user_id: string;
  peer_display_name: string;
  started_at: string;
  ended_at: string;
  duration_ms: number;
  lines: CallTranscriptLinePayload[];
}

export interface CallTranscriptPersistResponse {
  id: string;
  call_id: string;
}

/** Client → server WebSocket payloads. */
export type ClientCallMessage =
  | { type: "call.invite"; to_user_id: string }
  | { type: "call.cancel"; call_id: string }
  | { type: "call.accept"; call_id: string }
  | { type: "call.reject"; call_id: string }
  | { type: "call.hangup"; call_id: string }
  | { type: "rtc.offer"; call_id: string; sdp: string }
  | { type: "rtc.answer"; call_id: string; sdp: string }
  | { type: "rtc.ice"; call_id: string; candidate: RTCIceCandidateInit };

/** Server → client WebSocket payloads (subset used in task 112). */
export type ServerCallMessage =
  | { type: "connected"; user_id: string }
  | { type: "presence.snapshot"; online_user_ids: string[] }
  | { type: "presence.online"; user_id: string }
  | { type: "presence.offline"; user_id: string }
  | { type: "call.ringing"; call_id: string; to_user_id: string }
  | {
      type: "call.incoming";
      call_id: string;
      from_user_id: string;
      from_display_name: string;
    }
  | { type: "call.accepted"; call_id: string }
  | { type: "call.rejected"; call_id: string }
  | { type: "call.canceled"; call_id: string }
  | { type: "call.ended"; call_id: string; reason: string }
  | { type: "call.busy"; call_id: string }
  | { type: "call.failed"; call_id: string; code: string }
  | { type: "session.replaced" }
  | { type: "error"; code: string; message: string }
  | { type: "rtc.offer"; call_id: string; sdp: string }
  | { type: "rtc.answer"; call_id: string; sdp: string }
  | { type: "rtc.ice"; call_id: string; candidate: Record<string, unknown> };

export function isServerCallMessage(value: unknown): value is ServerCallMessage {
  return (
    typeof value === "object" &&
    value !== null &&
    "type" in value &&
    typeof (value as { type: unknown }).type === "string"
  );
}
