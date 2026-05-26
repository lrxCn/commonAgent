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
