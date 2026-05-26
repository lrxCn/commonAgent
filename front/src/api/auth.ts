import http from "@/api/http";
import type { LoginRequest, MeResponse } from "@/types";

export async function login(body: LoginRequest): Promise<MeResponse> {
  const { data } = await http.post<MeResponse>("/api/auth/login", body);
  return data;
}

export async function logout(): Promise<void> {
  await http.post("/api/auth/logout");
}

export async function fetchMe(): Promise<MeResponse> {
  const { data } = await http.get<MeResponse>("/api/me");
  return data;
}
