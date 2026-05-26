import http from "@/api/http";
import type {
  KbDocument,
  KbDocumentCreateRequest,
  KbDocumentDetail,
  KbDocumentListParams,
  KbDocumentListResponse,
  KbDocumentUpdateRequest,
} from "@/types";

export async function fetchKbDocuments(
  params: KbDocumentListParams = {},
): Promise<KbDocumentListResponse> {
  const { data } = await http.get<KbDocumentListResponse>("/api/admin/kb/documents", {
    params,
  });
  return data;
}

export async function fetchKbDocument(
  docId: string,
  roleId: string,
): Promise<KbDocumentDetail> {
  const { data } = await http.get<KbDocumentDetail>(`/api/admin/kb/documents/${docId}`, {
    params: { role_id: roleId },
  });
  return data;
}

export async function createKbDocument(body: KbDocumentCreateRequest): Promise<KbDocument> {
  const { data } = await http.post<KbDocument>("/api/admin/kb/documents", body);
  return data;
}

export async function updateKbDocument(
  docId: string,
  body: KbDocumentUpdateRequest,
): Promise<KbDocument> {
  const { data } = await http.patch<KbDocument>(`/api/admin/kb/documents/${docId}`, body);
  return data;
}

export async function deleteKbDocument(docId: string, roleId: string): Promise<void> {
  await http.delete(`/api/admin/kb/documents/${docId}`, {
    params: { role_id: roleId },
  });
}
