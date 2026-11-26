export interface ScoredPredictionItem {
  resource_id: string;
  identifier: string;
  risk_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  is_anomalous: boolean;
  anomaly_score: number;
  window_start: string;
  window_end: string;
}

export interface PredictionErrorItem {
  resource_id: string;
  identifier: string;
  code: 'no_new_prediction' | 'insufficient_history' | 'inference_error' | 'internal_error';
  error: string;
}

export interface PredictionRunResponse {
  outcome: 'full_success' | 'partial_success' | 'complete_failure';
  message?: string;
  scored_count: number;
  results: ScoredPredictionItem[];
  errors: PredictionErrorItem[];
}
