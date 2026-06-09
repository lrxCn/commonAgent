import http from "@/api/http";
import type {
  CallPeersResponse,
  CallTranscriptPayload,
  CallTranscriptPersistResponse,
} from "@/types/call";

export async function fetchPeers(): Promise<CallPeersResponse> {
  const { data } = await http.get<CallPeersResponse>("/api/calls/peers");
  return data;
}

export async function postCallTranscript(
  callId: string,
  payload: CallTranscriptPayload,
): Promise<CallTranscriptPersistResponse> {
  const { data } = await http.post<CallTranscriptPersistResponse>(
    `/api/calls/${encodeURIComponent(callId)}/transcript`,
    payload,
  );
  return data;
}
