export interface ModelEvaluationRow {
  label: string;
  threshold?: number;
  healthy: number; // percentage of healthy drives flagged
  failed: number;  // percentage of failed drives detected
}

export interface MLModelCard {
  id: string;
  name: string;
  version: string;
  model_type: 'FAILURE_PREDICTION' | 'ANOMALY_DETECTION';
  architecture: string;
  training_dataset: string;
  trained_at: string | null;
  is_active: boolean;
  thresholds: Record<string, number>;
  config: Record<string, any>;
  protocol?: string;
  rows: ModelEvaluationRow[];
  evaluation_metrics?: Record<string, any>;
}
