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
  is_admin?: boolean;
};

export type AdminUserUpdateRequest = {
  display_name?: string;
  password?: string;
  role_ids?: string[];
  is_admin?: boolean;
};
