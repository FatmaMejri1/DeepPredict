export type AlertType = 'FAILURE_RISK' | 'ANOMALY';
export type AlertStatus = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED';
export type AlertSeverity = 'HIGH' | 'CRITICAL';

export interface AlertResource {
  id: string;
  name: string;
  identifier: string;
  resource_type: string;
  status: string;
}

export interface AlertPrediction {
  id: number;
  model_type: string;
  score: number;
  risk_level: string | null;
  is_anomalous: boolean | null;
  window_start: string;
  window_end: string;
  created_at: string;
  model: {
    id: string;
    name: string;
    version: string;
    model_type: string;
    architecture: string;
  };
}

export interface Alert {
  id: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  status: AlertStatus;
  resource: AlertResource;
  first_seen_at: string;
  last_seen_at: string;
  occurrence_count: number;
  consecutive_clear_count: number;
  latest_prediction: AlertPrediction | null;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  resolution_source: 'AUTO' | 'USER' | '';
  created_at: string;
  updated_at: string;
}

export interface AlertFilters {
  status?: AlertStatus | '';
  alert_type?: AlertType | '';
  severity?: AlertSeverity | '';
  resource?: string;
}

export interface AlertPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: Alert[];
}

export interface AlertUnreadCount {
  count: number;
}
