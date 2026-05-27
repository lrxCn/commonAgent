import http from "@/api/http";
import type { CallPeersResponse } from "@/types/call";

export async function fetchPeers(): Promise<CallPeersResponse> {
  const { data } = await http.get<CallPeersResponse>("/api/calls/peers");
  return data;
}
