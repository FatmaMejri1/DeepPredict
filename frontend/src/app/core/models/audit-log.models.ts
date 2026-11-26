export type AuditAction =
  | 'LOGIN_SUCCESS'
  | 'LOGIN_FAILED'
  | 'LOGOUT'
  | 'CREATE'
  | 'UPDATE'
  | 'DELETE'
  | 'PREDICT_RUN'
  | 'CONFIG_CHANGE'
  | 'TELEMETRY_UPLOAD';

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  username: string;
  action: AuditAction;
  resource_type: string;
  resource_id: string;
}

export interface AuditLogFilters {
  username?: string;
  action?: AuditAction | '';
  date_from?: string;
  date_to?: string;
}

export interface AuditLogPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: AuditLogEntry[];
}
