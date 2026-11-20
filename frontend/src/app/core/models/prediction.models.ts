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
  error: string;
}

export interface PredictionRunResponse {
  scored_count: number;
  results: ScoredPredictionItem[];
  errors: PredictionErrorItem[];
}
