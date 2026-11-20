import { Role } from './auth.models';

export interface DriveSummaryItem {
  id: string;
  name: string;
  identifier: string;
  model: string;
  vendor: string;
  datacenter: string;
  status: 'HEALTHY' | 'WARNING' | 'HIGH_RISK';
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | null;
  risk_score: number | null;
  scored_until: string | null;
  is_anomalous: boolean;
  last_reading: string | null;
}

export interface DashboardSummary {
  total: number;
  healthy: number;
  warning: number;
  high_risk: number;
  anomalous: number;
  not_scored: number;
  data_until: string | null;
  top_critical: DriveSummaryItem[];
}

export interface DashboardActivityItem {
  id: number;
  drive_identifier: string;
  drive_name: string;
  kind: 'Failure risk' | 'Anomaly detection';
  outcome: string;
  score: number;
  created_at: string;
}

export interface DashboardActivityResponse {
  results: DashboardActivityItem[];
}

export interface InferenceServiceHealth {
  status: 'online' | 'offline';
  model_version: string | null;
  checked_at: string;
}
