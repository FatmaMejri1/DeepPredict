export interface Drive {
  id: string;
  name: string;
  identifier: string;
  model: string;
  vendor: string;
  datacenter: string;
  capacity_bytes?: number;
  status: 'HEALTHY' | 'WARNING' | 'HIGH_RISK';
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | null;
  risk_score: number | null;
  scored_until: string | null;
  is_anomalous: boolean;
  anomaly_evaluated: boolean;
  last_reading: string | null;
}

export interface DriveDetail extends Drive {
  attributes: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface SmartSeriesItem {
  label: string;
  values: (number | null)[];
}

export interface SmartChartData {
  labels: string[];
  series: SmartSeriesItem[];
}

export interface RiskChartData {
  labels: string[];
  scores: number[];
}

export interface RiskThresholds {
  medium?: number;
  high?: number;
  critical?: number;
  anomaly?: number;
}

export interface DriveTelemetryData {
  smart: SmartChartData;
  risk: RiskChartData;
  thresholds: RiskThresholds;
}

export interface DrivePredictionHistoryItem {
  id: number;
  prediction_type: 'FAILURE_PREDICTION' | 'ANOMALY_DETECTION';
  score: number;
  risk_level: string | null;
  is_anomalous: boolean | null;
  horizon_days: number | null;
  window_start: string;
  window_end: string;
  created_at: string;
  model: {
    name: string;
    version: string;
    model_type: string;
    architecture: string;
  };
}

export type DriveTimelineEventType =
  | 'TELEMETRY_READING'
  | 'PREDICTION'
  | 'ALERT_OPENED'
  | 'ALERT_ACKNOWLEDGED'
  | 'ALERT_RESOLVED'
  | 'RESOURCE_AUDIT';

export interface DriveTimelineEvent {
  id: string;
  event_type: DriveTimelineEventType;
  occurred_at: string;
  resource: Pick<Drive, 'id' | 'name' | 'identifier'>;
  actor: string | null;
  data: {
    source?: string;
    prediction_type?: 'FAILURE_PREDICTION' | 'ANOMALY_DETECTION';
    score?: number;
    risk_level?: string | null;
    is_anomalous?: boolean | null;
    horizon_days?: number | null;
    window_start?: string;
    window_end?: string;
    model?: {
      name: string;
      version: string;
      model_type: string;
      architecture: string;
    };
    alert_id?: string;
    alert_type?: 'FAILURE_RISK' | 'ANOMALY';
    severity?: 'HIGH' | 'CRITICAL';
    resolution_source?: 'AUTO' | 'USER';
    action?: string;
    description?: string;
  };
}

export interface DriveTimelinePage {
  count: number;
  next: string | null;
  previous: string | null;
  results: DriveTimelineEvent[];
}

export interface DriveTimelineQuery {
  page: number;
  page_size: number;
  type?: DriveTimelineEventType | '';
  from?: string;
  to?: string;
}
