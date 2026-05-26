import http from "@/api/http";
import type {
  AdminRole,
  AdminRoleCreateRequest,
  AdminRoleUpdateRequest,
  AdminUser,
  AdminUserCreateRequest,
  AdminUserUpdateRequest,
} from "@/types";

export async function fetchRoles(): Promise<AdminRole[]> {
  const { data } = await http.get<AdminRole[]>("/api/admin/roles");
  return data;
}

export async function createRole(body: AdminRoleCreateRequest): Promise<AdminRole> {
  const { data } = await http.post<AdminRole>("/api/admin/roles", body);
  return data;
}

export async function updateRole(
  roleId: string,
  body: AdminRoleUpdateRequest,
): Promise<AdminRole> {
  const { data } = await http.patch<AdminRole>(`/api/admin/roles/${roleId}`, body);
  return data;
}

export async function deleteRole(roleId: string): Promise<void> {
  await http.delete(`/api/admin/roles/${roleId}`);
}

export async function fetchUsers(): Promise<AdminUser[]> {
  const { data } = await http.get<AdminUser[]>("/api/admin/users");
  return data;
}

export async function createUser(body: AdminUserCreateRequest): Promise<AdminUser> {
  const { data } = await http.post<AdminUser>("/api/admin/users", body);
  return data;
}

export async function updateUser(
  userId: string,
  body: AdminUserUpdateRequest,
): Promise<AdminUser> {
  const { data } = await http.patch<AdminUser>(`/api/admin/users/${userId}`, body);
  return data;
}

export async function deleteUser(userId: string): Promise<void> {
  await http.delete(`/api/admin/users/${userId}`);
}
