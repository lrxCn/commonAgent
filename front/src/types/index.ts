/** Shared API and domain types (expanded in later demo tasks). */

export type ApiErrorBody = {
  code: string;
  message: string;
};

export type MeResponse = {
  user_id: string;
  username: string;
  display_name: string;
  role_ids: string[];
  is_admin: boolean;
};
