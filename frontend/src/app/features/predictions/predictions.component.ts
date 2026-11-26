import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { PredictionService } from '../../core/services/prediction.service';
import { PredictionRunResponse } from '../../core/models/prediction.models';
import { ModelService } from '../../core/services/model.service';
import { MLModelCard } from '../../core/models/model.models';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-predictions',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="predictions-page">
      <div class="page-header">
        <div>
          <h1 class="page-title">AI Inference Engine</h1>
          <p class="page-subtitle">Multi-model predictive pipeline combining sequence forecasting and telemetry anomaly detection.</p>
        </div>
        <div class="header-action" *ngIf="isITProOrSysAdmin()">
          <button class="btn btn-primary" (click)="onRunAllInference()" [disabled]="running">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            <span>{{ running ? 'Executing AI Inference...' : 'Run Fleet Batch Inference' }}</span>
          </button>
        </div>
      </div>

      <!-- Architecture Comparison Banner -->
      <div class="card comparison-card">
        <div class="card-header">
          <h3>Dual-Model Inference Architecture</h3>
          <span class="badge badge-neutral">Independent Analytical Pipelines</span>
        </div>
        <div class="models-grid">
          <div class="model-column gru">
            <div class="model-badge">MODEL 1: RISK_GRU.PT</div>
            <h4>Gated Recurrent Unit (GRU) Failure Forecasting</h4>
            <p>
              Supervised sequence model predicting whether a drive will fail within a <strong>7-day prediction horizon</strong>.
            </p>
            <div class="model-constraint-tag">
              Output: <strong>Ranking Score [0.0 - 1.0]</strong> (relative failure urgency, not probability)
            </div>
            <div class="thresholds-tag">
              Active model thresholds: {{ thresholdSummary('FAILURE_PREDICTION') }}
            </div>
          </div>

          <div class="model-column lstm">
            <div class="model-badge">MODEL 2: ANOMALY_LSTMAE.PT</div>
            <h4>LSTM Autoencoder (LSTM-AE) Outlier Detection</h4>
            <p>
              Unsupervised deep autoencoder measuring telemetry reconstruction error to flag <strong>physical degradation anomalies</strong>.
            </p>
            <div class="model-constraint-tag">
              Output: <strong>Reconstruction Error</strong> compared with the active anomaly threshold
            </div>
            <div class="thresholds-tag">
              Active model threshold: {{ thresholdSummary('ANOMALY_DETECTION') }}. Evaluates anomalies independently of failure timing.
            </div>
          </div>
        </div>
      </div>

      <!-- Execution Status / Summary -->
      <div *ngIf="runErrorMessage" class="execution-outcome outcome-failure" role="alert">
        {{ runErrorMessage }}
      </div>
      <div *ngIf="lastResponse" class="execution-outcome" role="status"
        [class.outcome-success]="lastResponse.outcome === 'full_success'"
        [class.outcome-partial]="lastResponse.outcome === 'partial_success'"
        [class.outcome-failure]="lastResponse.outcome === 'complete_failure'">
        {{ outcomeMessage(lastResponse) }}
      </div>
      <div class="card execution-summary-card" *ngIf="lastResponse">
        <div class="card-header">
          <h3>Batch Inference Summary</h3>
          <span class="badge" [class.badge-passed]="lastResponse.outcome === 'full_success'"
            [class.badge-warning]="lastResponse.outcome !== 'full_success'">
            {{ lastResponse.scored_count }} Drives Scored
          </span>
        </div>
        <div class="summary-body">
          <div class="summary-stat">
            <span class="stat-label">SUCCESSFULLY SCORED</span>
            <span class="stat-val font-mono">{{ lastResponse.scored_count }}</span>
          </div>
          <div class="summary-stat">
            <span class="stat-label">FAILED OR NOT SCORED</span>
            <span class="stat-val font-mono" [class.text-warning]="lastResponse.errors.length > 0">{{ lastResponse.errors.length }}</span>
          </div>
        </div>
      </div>

      <!-- Results Table -->
      <div class="card results-card" *ngIf="lastResponse && lastResponse.results.length > 0">
        <div class="card-header">
          <h3>Scored Predictions Output</h3>
        </div>
        <div class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Drive Serial / ID</th>
                <th>Failure Risk Level</th>
                <th>Risk Ranking Score</th>
                <th>Anomaly Detection</th>
                <th>Anomaly Reconstruction Error</th>
                <th>Telemetry Window Start</th>
                <th>Telemetry Window End</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let item of lastResponse.results">
                <td>
                  <a [routerLink]="['/drives', item.resource_id]" class="drive-link font-mono font-bold">
                    {{ item.identifier }}
                  </a>
                </td>
                <td>
                  <span class="badge"
                    [class.badge-low]="item.risk_level === 'LOW'"
                    [class.badge-medium]="item.risk_level === 'MEDIUM'"
                    [class.badge-high]="item.risk_level === 'HIGH'"
                    [class.badge-critical]="item.risk_level === 'CRITICAL'">
                    {{ item.risk_level }}
                  </span>
                </td>
                <td>
                  <span class="font-mono font-bold">{{ item.risk_score | number:'1.3-3' }}</span>
                </td>
                <td>
                  <span class="badge" [class.badge-anomaly]="item.is_anomalous" [class.badge-neutral]="!item.is_anomalous">
                    {{ item.is_anomalous ? 'ANOMALOUS' : 'NORMAL' }}
                  </span>
                </td>
                <td class="font-mono">{{ item.anomaly_score | number:'1.4-4' }}</td>
                <td class="text-muted">{{ item.window_start | date:'yyyy-MM-dd' }}</td>
                <td class="text-muted">{{ item.window_end | date:'yyyy-MM-dd' }}</td>
                <td>
                  <a [routerLink]="['/drives', item.resource_id]" class="btn btn-secondary btn-sm">Inspect Drive</a>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Skipped / Constraints Warnings Table -->
      <div class="card errors-card" *ngIf="lastResponse && lastResponse.errors.length > 0">
        <div class="card-header">
          <h3>Failed or Skipped Drives</h3>
        </div>
        <div class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Drive Serial / ID</th>
                <th>Outcome</th>
                <th>Explanation</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let err of lastResponse.errors">
                <td class="font-mono">{{ err.identifier }}</td>
                <td><span class="badge" [class.badge-warning]="isSkipped(err.code)"
                  [class.badge-critical]="!isSkipped(err.code)">{{ isSkipped(err.code) ? 'SKIPPED' : 'FAILED' }}</span></td>
                <td class="text-muted">{{ err.error }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .predictions-page {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }

    .execution-outcome {
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      padding: 0.85rem 1rem;
      font-weight: 600;
    }
    .outcome-success { color: var(--success); background: rgba(16, 185, 129, 0.08); }
    .outcome-partial { color: var(--warning); background: rgba(245, 158, 11, 0.1); }
    .outcome-failure { color: var(--danger); background: rgba(239, 68, 68, 0.08); }

    .page-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 1rem;

      .page-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #0f172a;
      }
      .page-subtitle {
        font-size: 0.875rem;
        color: var(--text-muted);
        margin-top: 0.25rem;
      }
    }

    .comparison-card {
      .models-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 1.5rem;
        margin-top: 0.5rem;

        .model-column {
          padding: 1.25rem;
          border-radius: var(--radius-sm);
          border: 1px solid var(--border-color);
          display: flex;
          flex-direction: column;
          gap: 0.5rem;

          &.gru {
            background: #f8fafc;
            border-top: 4px solid var(--primary);
          }

          &.lstm {
            background: #f8fafc;
            border-top: 4px solid var(--anomaly);
          }

          .model-badge {
            font-size: 0.7rem;
            font-weight: 700;
            color: var(--text-muted);
            letter-spacing: 0.05em;
          }

          h4 {
            font-size: 1rem;
            font-weight: 600;
            color: #0f172a;
          }

          p {
            font-size: 0.825rem;
            color: var(--text-muted);
            line-height: 1.4;
          }

          .model-constraint-tag {
            font-size: 0.8rem;
            color: #1e3a8a;
            background: #eff6ff;
            padding: 0.4rem 0.65rem;
            border-radius: 4px;
            margin-top: 0.5rem;
          }

          .thresholds-tag {
            font-size: 0.75rem;
            color: var(--text-muted);
          }
        }
      }
    }

    .execution-summary-card {
      .summary-body {
        display: flex;
        gap: 2rem;
        margin-top: 0.5rem;

        .summary-stat {
          display: flex;
          flex-direction: column;
          .stat-label { font-size: 0.7rem; font-weight: 700; color: var(--text-muted); }
          .stat-val { font-size: 1.75rem; font-weight: 700; color: #0f172a; }
          .text-warning { color: #f59e0b; }
        }
      }
    }

    .font-mono {
      font-family: ui-monospace, SFMono-Regular, monospace;
    }
    .font-bold { font-weight: 700; }
    .drive-link {
      color: var(--primary);
      &:hover { text-decoration: underline; }
    }
  `],
})
export class PredictionsComponent implements OnInit {
  private predictionService = inject(PredictionService);
  private modelService = inject(ModelService);
  private authService = inject(AuthService);

  readonly isITProOrSysAdmin = this.authService.isITProOrSysAdmin;

  running = false;
  lastResponse: PredictionRunResponse | null = null;
  runErrorMessage = '';
  models: MLModelCard[] = [];

  ngOnInit(): void {
    this.modelService.getModels().subscribe({
      next: (models) => { this.models = models; },
      error: () => { this.models = []; },
    });
  }

  thresholdSummary(modelType: MLModelCard['model_type']): string {
    const model = this.models.find((candidate) => candidate.model_type === modelType && candidate.is_active);
    if (!model) return 'Unavailable';
    const available = Object.entries(model.thresholds ?? {}).filter(
      ([, value]) => typeof value === 'number' && Number.isFinite(value),
    );
    return available.length
      ? available.map(([name, value]) => `${name.toUpperCase()} (${value})`).join(', ')
      : 'Unavailable';
  }

  outcomeMessage(response: PredictionRunResponse): string {
    if (response.outcome === 'full_success') {
      return 'All requested drives were scored successfully.';
    }
    if (response.outcome === 'partial_success') {
      return `Partial success: ${response.scored_count} drives scored; ${response.errors.length} could not be scored.`;
    }
    return response.message || 'Prediction run failed. No drives were successfully scored.';
  }

  isSkipped(code: string): boolean {
    return code === 'no_new_prediction' || code === 'insufficient_history';
  }

  onRunAllInference(): void {
    this.running = true;
    this.lastResponse = null;
    this.runErrorMessage = '';
    this.predictionService.runPrediction().subscribe({
      next: (resp) => {
        this.lastResponse = resp;
        this.running = false;
      },
      error: (error) => {
        const response = error?.error as PredictionRunResponse | undefined;
        if (response && ['full_success', 'partial_success', 'complete_failure'].includes(response.outcome)
            && Array.isArray(response.results) && Array.isArray(response.errors)) {
          this.lastResponse = response;
        } else {
          this.runErrorMessage = 'The prediction request could not be completed. Please try again.';
        }
        this.running = false;
      },
    });
  }
}
