/** Shared API and domain types. */

export type ApiErrorBody = {
  code: string;
  message: string;
  field_errors?: Record<string, string>;
};

export type RoleSummary = {
  role_id: string;
  name: string;
};

export type MeResponse = {
  user_id: string;
  username: string;
  display_name: string;
  role_ids: string[];
  is_admin: boolean;
  roles: RoleSummary[];
};

export type LoginRequest = {
  username: string;
  password: string;
};

export type Student = {
  student_id: string;
  student_no: string;
  name: string;
  class_name: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type StudentListResponse = {
  items: Student[];
  total: number;
  offset: number;
  limit: number;
};

export type StudentCreateRequest = {
  student_no: string;
  name: string;
  class_name?: string | null;
  status?: string;
};

export type StudentUpdateRequest = Partial<StudentCreateRequest>;

export type StudentListParams = {
  offset?: number;
  limit?: number;
  search?: string;
  status?: string;
  class_name?: string;
};

export type AdminRole = {
  role_id: string;
  name: string;
  description: string | null;
  user_count: number;
  document_count: number;
  created_at: string;
  updated_at: string;
};

export type AdminRoleCreateRequest = {
  role_id: string;
  name: string;
  description?: string | null;
};

export type AdminRoleUpdateRequest = {
  name?: string;
  description?: string | null;
};

export type AdminUser = {
  user_id: string;
  username: string;
  display_name: string;
  is_admin: boolean;
  role_ids: string[];
  roles: RoleSummary[];
  created_at: string;
  updated_at: string;
};

export type AdminUserCreateRequest = {
  username: string;
  password: string;
  display_name: string;
  role_ids: string[];
};

export type AdminUserUpdateRequest = {
  display_name?: string;
  password?: string;
  role_ids?: string[];
};

export type KbChunk = {
  chunk_id: string;
  index: number;
  text: string;
};

export type KbDocument = {
  doc_id: string;
  role_ids: string[];
  doc_name: string;
  version: string;
  raw_content: string;
  chunks_written: number;
  tokens_estimated: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type KbDocumentDetail = KbDocument & {
  chunks: KbChunk[];
};

export type KbDocumentListResponse = {
  items: KbDocument[];
  total: number;
  offset: number;
  limit: number;
};

export type KbDocumentListParams = {
  role_id?: string;
  keyword?: string;
  offset?: number;
  limit?: number;
};

export type KbDocumentCreateRequest = {
  role_ids: string[];
  doc_name: string;
  content: string;
  doc_id?: string;
  version?: string;
};

export type KbDocumentUpdateRequest = {
  role_ids?: string[];
  doc_name?: string;
  raw_content?: string;
  version?: string;
};

export type ClientAction = {
  tool: string;
  args: Record<string, unknown>;
  requires_approval: boolean;
};

export type JumpPageArgs = {
  page: string;
};

export type ChatJsonResponse = {
  text: string | null;
  client_actions: ClientAction[] | null;
};

export type HistoryMessageItem = {
  message_id: string | null;
  role: "human" | "ai" | "system" | "tool" | "other";
  content: string;
  timestamp: string | null;
  client_actions: ClientAction[] | null;
};

export type HistoryMessagesResponse = {
  items: HistoryMessageItem[];
  next_cursor: string | null;
};

export type ChatDisplayRole = "human" | "ai" | "system";

export type ChatDisplayMessage = {
  id: string;
  role: ChatDisplayRole;
  content: string;
  streaming?: boolean;
};
