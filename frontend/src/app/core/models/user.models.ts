import { Role } from './auth.models';

export interface UserListItem {
  id: string;
  username: string;
  email: string;
  role: Role;
  role_display?: string;
  is_active: boolean;
  date_joined: string;
  last_login?: string | null;
}

export interface CreateUserPayload {
  username: string;
  email: string;
  password: string;
  role: Role;
}

export interface UpdateUserPayload {
  email?: string;
  role?: Role;
  is_active?: boolean;
}
