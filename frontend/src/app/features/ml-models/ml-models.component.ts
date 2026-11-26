import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ModelService } from '../../core/services/model.service';
import { MLModelCard } from '../../core/models/model.models';

@Component({
  selector: 'app-ml-models',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="models-page">
      <div class="page-header">
        <div>
          <h1 class="page-title">Machine Learning Model Registry</h1>
          <p class="page-subtitle">Production model architectures, training configurations, and empirical evaluation benchmarks.</p>
        </div>
      </div>

      <!-- Conceptual Distinction Banner -->
      <div class="card note-card">
        <div class="note-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
        </div>
        <div>
          <h4>Important Model Characteristics</h4>
          <p class="note-text">
            <strong>Ranking Score:</strong> The failure risk model outputs a relative severity ranking index, NOT an absolute Bayesian probability of failure.
            <strong>Separation of Analyses:</strong> Anomaly detection (unsupervised reconstruction deviation) and failure prediction (supervised sequence forecasting) operate independently.
          </p>
        </div>
      </div>

      <div *ngIf="loading" class="dashboard-state loading-state" role="status">Loading model records…</div>
      <div *ngIf="error" class="dashboard-state error-state" role="alert">
        <span>{{ error }}</span>
        <button type="button" class="btn btn-secondary btn-sm" (click)="loadModels()">Try again</button>
      </div>
      <div *ngIf="!loading && !error && models.length === 0" class="dashboard-state empty-state">
        No registered model versions are available.
      </div>

      <!-- Models List -->
      <div class="models-list" *ngIf="!loading && !error && models.length > 0">
        <div class="card model-card" *ngFor="let model of models">
          <div class="card-header">
            <div class="model-title-row">
              <h3>{{ model.name }}</h3>
              <span class="version-tag font-mono">v{{ model.version }}</span>
              <span class="badge" [class.badge-healthy]="model.is_active" [class.badge-neutral]="!model.is_active">
                {{ model.is_active ? 'ACTIVE IN PRODUCTION' : 'INACTIVE' }}
              </span>
            </div>
            <span class="badge" [class.badge-primary]="model.model_type === 'FAILURE_PREDICTION'" [class.badge-anomaly]="model.model_type === 'ANOMALY_DETECTION'">
              {{ model.model_type === 'FAILURE_PREDICTION' ? 'FAILURE FORECASTING' : 'ANOMALY DETECTION' }}
            </span>
          </div>

          <div class="model-metadata-grid">
            <div class="meta-box">
              <span class="label">NEURAL ARCHITECTURE</span>
              <span class="value font-mono">{{ model.architecture }}</span>
            </div>
            <div class="meta-box">
              <span class="label">TRAINING DATASET</span>
              <span class="value">{{ model.training_dataset }}</span>
            </div>
            <div class="meta-box">
              <span class="label">TRAINED AT</span>
              <span class="value">{{ model.trained_at ? (model.trained_at | date:'mediumDate') : '—' }}</span>
            </div>
            <div class="meta-box">
              <span class="label">INPUT WINDOW</span>
              <span class="value">14 Sequential Days</span>
            </div>
          </div>

          <!-- Thresholds & Parameters -->
          <div class="thresholds-section">
            <h4>Calibrated Decision Thresholds</h4>
            <div class="thresholds-pills">
              <div class="thresh-pill" *ngFor="let entry of model.thresholds | keyvalue">
                <span class="thresh-key">{{ entry.key | uppercase }}:</span>
                <span class="thresh-val font-mono">{{ entry.value }}</span>
              </div>
            </div>
          </div>

          <!-- Evaluation Performance Table -->
          <div class="eval-table-section" *ngIf="model.rows?.length">
            <div class="eval-header">
              <h4>Empirical Validation Benchmarks</h4>
              <span class="protocol-text" *ngIf="model.protocol">Protocol: {{ model.protocol }}</span>
            </div>

            <div class="table-container">
              <table class="table">
                <thead>
                  <tr>
                    <th>Operating Tier / Threshold</th>
                    <th>Calibrated Cutoff</th>
                    <th>Failed Drives Detected</th>
                    <th>Healthy Drives Flagged (False Positives)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr *ngFor="let row of model.rows">
                    <td>
                      <span class="badge"
                        [class.badge-low]="row.label === 'LOW'"
                        [class.badge-medium]="row.label === 'MEDIUM'"
                        [class.badge-high]="row.label === 'HIGH'"
                        [class.badge-critical]="row.label === 'CRITICAL'"
                        [class.badge-anomaly]="row.label === 'ANOMALOUS'">
                        {{ row.label }}
                      </span>
                    </td>
                    <td class="font-mono">{{ row.threshold !== undefined ? row.threshold : '—' }}</td>
                    <td class="text-success font-bold font-mono">
                      {{ row.failed | number:'1.1-1' }}%
                    </td>
                    <td class="text-muted font-mono">
                      {{ row.healthy | number:'1.2-2' }}%
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <section class="evaluation-data" aria-label="Recorded model evaluation metrics">
            <h4>{{ model.model_type === 'FAILURE_PREDICTION' ? 'GRU failure-risk evaluation data' : 'LSTM Autoencoder anomaly evaluation data' }}</h4>
            <pre *ngIf="hasEvaluationMetrics(model)">{{ model.evaluation_metrics | json }}</pre>
            <p *ngIf="!hasEvaluationMetrics(model)" class="text-muted">No evaluation metrics recorded for this model version.</p>
          </section>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .models-page {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }

    .page-header {
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

    .note-card {
      display: flex;
      gap: 1rem;
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      padding: 1.25rem;

      .note-icon {
        color: #2563eb;
      }

      h4 {
        font-size: 0.95rem;
        font-weight: 600;
        color: #1e3a8a;
        margin-bottom: 0.25rem;
      }

      .note-text {
        font-size: 0.825rem;
        color: #1e40af;
        line-height: 1.4;
      }
    }

    .models-list {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;

      .model-card {
        .model-title-row {
          display: flex;
          align-items: center;
          gap: 0.75rem;

          .version-tag {
            font-size: 0.8rem;
            background: #f1f5f9;
            padding: 0.15rem 0.45rem;
            border-radius: 4px;
            color: #475569;
          }
        }

        .model-metadata-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 1rem;
          margin-bottom: 1.25rem;

          .meta-box {
            background: #f8fafc;
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            padding: 0.75rem;
            display: flex;
            flex-direction: column;

            .label {
              font-size: 0.65rem;
              font-weight: 700;
              color: var(--text-muted);
            }
            .value {
              font-size: 0.875rem;
              font-weight: 600;
              color: #0f172a;
              margin-top: 0.2rem;
            }
          }
        }

        .thresholds-section {
          margin-bottom: 1.5rem;

          h4 {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
          }

          .thresholds-pills {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;

            .thresh-pill {
              background: #ffffff;
              border: 1px solid var(--border-color);
              border-radius: var(--radius-sm);
              padding: 0.35rem 0.65rem;
              font-size: 0.8rem;
              display: flex;
              gap: 0.35rem;

              .thresh-key { font-weight: 600; color: #475569; }
              .thresh-val { font-weight: 700; color: var(--primary); }
            }
          }
        }

        .eval-table-section {
          .eval-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.5rem;

            h4 {
              font-size: 0.85rem;
              font-weight: 600;
              color: var(--text-muted);
              text-transform: uppercase;
              letter-spacing: 0.05em;
            }

            .protocol-text {
              font-size: 0.75rem;
              color: var(--text-muted);
            }
          }
        }
      }
    }

    .evaluation-data {
      margin-top: 1.25rem;
      padding-top: 1rem;
      border-top: 1px solid var(--border-color);

      h4 { margin-bottom: 0.5rem; font-size: 0.85rem; color: var(--text-main); }
      pre {
        margin: 0;
        padding: 0.75rem;
        max-height: 16rem;
        overflow: auto;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        background: #f8fafc;
        border: 1px solid var(--border-color);
        border-radius: var(--radius-sm);
        color: var(--text-main);
        font-size: 0.75rem;
      }
    }

    .font-mono {
      font-family: ui-monospace, SFMono-Regular, monospace;
    }
    .font-bold { font-weight: 700; }
    .text-success { color: #10b981; }
  `],
})
export class MlModelsComponent implements OnInit {
  private modelService = inject(ModelService);

  models: MLModelCard[] = [];
  loading = true;
  error = '';

  ngOnInit(): void {
    this.loadModels();
  }

  loadModels(): void {
    this.loading = true;
    this.error = '';
    this.modelService.getModels().subscribe({
      next: (data) => {
        this.models = data;
        this.loading = false;
      },
      error: () => {
        this.models = [];
        this.loading = false;
        this.error = 'Model information could not be loaded.';
      },
    });
  }

  hasEvaluationMetrics(model: MLModelCard): boolean {
    return !!model.evaluation_metrics && Object.keys(model.evaluation_metrics).length > 0;
  }
}
