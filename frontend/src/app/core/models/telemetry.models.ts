export interface ValidationCheck {
  name: string;
  status: 'passed' | 'warning' | 'error';
  message: string;
  details?: any;
}

export interface ValidationReport {
  ready_for_prediction: boolean;
  history_valid: boolean;
  model_compatibility_verified: boolean;
  checks: ValidationCheck[];
  errors: string[];
  warnings: string[];
  metrics: {
    total_readings: number;
    calendar_days: number;
    missing_days: number;
    available_features: number;
    [key: string]: any;
  };
  recommendations: string[];
}

export interface TelemetryUploadResponse {
  status: string;
  ingested_readings: number;
  drives_affected: string[];
  error?: string;
}
