export type Role = 'SYSADMIN' | 'IT_PRO' | 'OPERATOR';

export interface User {
  id: string;
  username: string;
  email: string;
  role: Role;
  role_display?: string;
  is_active: boolean;
  date_joined?: string;
  last_login?: string | null;
}

export interface LoginResponse {
  access: string;
  refresh: string;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}
