import { ChangeDetectorRef, Component, ElementRef, OnInit, ViewChild, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { Chart, registerables } from 'chart.js';
import { DriveService } from '../../../core/services/drive.service';
import { PredictionService } from '../../../core/services/prediction.service';
import { DriveDetail, DrivePredictionHistoryItem, DriveTelemetryData } from '../../../core/models/drive.models';
import { AuthService } from '../../../core/services/auth.service';

Chart.register(...registerables);

@Component({
  selector: 'app-drive-detail',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="drive-detail-page" *ngIf="drive">
      <!-- Breadcrumb & Navigation -->
      <div class="top-nav">
        <a routerLink="/drives" class="back-link">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
          Back to Drive Inventory
        </a>
      </div>

      <!-- Drive Header -->
      <div class="drive-header-card card">
        <div class="header-main">
          <div class="drive-identity">
            <div class="drive-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect width="20" height="8" x="2" y="3" rx="2"/><rect width="20" height="8" x="2" y="13" rx="2"/>
                <circle cx="6" cy="7" r="1" fill="currentColor"/><circle cx="6" cy="17" r="1" fill="currentColor"/>
              </svg>
            </div>
            <div>
              <div class="id-row">
                <h1 class="drive-title font-mono">{{ drive.identifier }}</h1>
                <span class="badge" [class.badge-healthy]="drive.status === 'HEALTHY'" [class.badge-warning]="drive.status === 'WARNING'" [class.badge-high_risk]="drive.status === 'HIGH_RISK'">
                  {{ drive.status }}
                </span>
              </div>
              <div class="specs-row">
                <span>Model: <strong>{{ drive.model || 'Unknown' }}</strong></span>
                <span>Vendor: <strong>{{ drive.vendor || 'Unknown' }}</strong></span>
                <span>Datacenter: <strong>{{ drive.datacenter || 'N/A' }}</strong></span>
              </div>
            </div>
          </div>

          <div class="header-action" *ngIf="isITProOrSysAdmin()">
            <button class="btn btn-primary" (click)="onScoreDrive()" [disabled]="scoring">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
              <span>{{ scoring ? 'Scoring with AI...' : 'Run Prediction Now' }}</span>
            </button>
          </div>
        </div>

        <div *ngIf="scoreMessage" class="score-alert" [class.score-success]="!scoreError" [class.score-error]="scoreError">
          {{ scoreMessage }}
        </div>
      </div>

      <!-- Dual AI Assessment Overview -->
      <div class="assessment-grid">
        <!-- 1. Failure Prediction Card -->
        <div class="card assessment-card">
          <div class="card-header">
            <div>
              <h3>GRU Failure Forecasting</h3>
              <span class="subtext">7-day failure horizon prediction</span>
            </div>
            <span class="badge"
              [class.badge-low]="drive.risk_level === 'LOW'"
              [class.badge-medium]="drive.risk_level === 'MEDIUM'"
              [class.badge-high]="drive.risk_level === 'HIGH'"
              [class.badge-critical]="drive.risk_level === 'CRITICAL'"
              [class.badge-neutral]="!drive.risk_level">
              {{ drive.risk_level || 'NOT SCORED' }}
            </span>
          </div>

          <div class="score-stat">
            <div class="stat-number font-mono" *ngIf="drive.risk_score !== null">
              {{ drive.risk_score | number:'1.3-3' }}
            </div>
            <div class="stat-number text-muted" *ngIf="drive.risk_score === null">
              —
            </div>
            <div class="stat-info">
              <strong>Failure-Risk Score</strong>
              <p class="model-note">
                Relative ranking index (not an absolute failure probability). Calibrated for prioritised disk replacement.
              </p>
            </div>
          </div>
        </div>

        <!-- 2. Anomaly Detection Card -->
        <div class="card assessment-card">
          <div class="card-header">
            <div>
              <h3>LSTM-AE Anomaly Detection</h3>
              <span class="subtext">Unsupervised reconstruction error</span>
            </div>
            <span class="badge" [class.badge-anomaly]="drive.is_anomalous" [class.badge-neutral]="!drive.is_anomalous">
              {{ drive.is_anomalous ? 'ANOMALY DETECTED' : 'NORMAL PATTERN' }}
            </span>
          </div>

          <div class="score-stat">
            <div class="stat-icon" [class.anomaly-icon]="drive.is_anomalous">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z"/>
                <path d="M12 8v4M12 16h.01"/>
              </svg>
            </div>
            <div class="stat-info">
              <strong>Telemetry Deviation Analysis</strong>
              <p class="model-note">
                Flags unusual physical degradation signatures that differ significantly from historical baseline behavior.
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Time-Series Charts Grid -->
      <div class="charts-grid">
        <!-- Chart 1: SMART Physical Degradation Counters -->
        <div class="card chart-card">
          <div class="card-header">
            <div>
              <h3>SMART Physical Degradation Counters</h3>
              <p class="chart-subtitle">Reallocated Sectors (5), Uncorrectable Errors (187), Pending Sectors (197)</p>
            </div>
          </div>
          <div class="canvas-wrapper">
            <canvas #smartCanvas></canvas>
          </div>
        </div>

        <!-- Chart 2: Failure-Risk Score History vs Decision Thresholds -->
        <div class="card chart-card">
          <div class="card-header">
            <div>
              <h3>Historical Failure-Risk Score vs Calibrated Thresholds</h3>
              <p class="chart-subtitle">Thresholds: Medium (0.35), High (0.60), Critical (0.80)</p>
            </div>
          </div>
          <div class="canvas-wrapper">
            <canvas #riskCanvas></canvas>
          </div>
        </div>
      </div>

      <!-- Drive Metadata -->
      <div class="card metadata-card">
        <div class="card-header">
          <h3>Hardware Specifications & Metadata</h3>
        </div>
        <div class="meta-grid">
          <div class="meta-item">
            <span class="meta-label">Identifier / Serial:</span>
            <span class="meta-val font-mono">{{ drive.identifier }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Capacity:</span>
            <span class="meta-val">{{ formatCapacity(drive.capacity_bytes) }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Scored Horizon End:</span>
            <span class="meta-val">{{ drive.scored_until ? (drive.scored_until | date:'medium') : 'Not yet scored' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Latest SMART Telemetry:</span>
            <span class="meta-val">{{ drive.last_reading ? (drive.last_reading | date:'medium') : 'No readings' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Registered in DeepPredict:</span>
            <span class="meta-val">{{ drive.created_at | date:'medium' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Status Last Updated:</span>
            <span class="meta-val">{{ drive.updated_at | date:'medium' }}</span>
          </div>
        </div>
      </div>

      <section class="card history-card" aria-labelledby="prediction-history-title">
        <div class="card-header">
          <h3 id="prediction-history-title">Prediction history</h3>
        </div>
        <p *ngIf="historyLoading" role="status">Loading prediction history…</p>
        <p *ngIf="historyError" class="text-muted" role="alert">Prediction history could not be loaded.</p>
        <p *ngIf="!historyLoading && !historyError && predictionHistory.length === 0" class="text-muted">
          No predictions yet for this drive.
        </p>
        <div class="history-table-wrap" *ngIf="!historyLoading && predictionHistory.length > 0">
          <table class="history-table">
            <thead>
              <tr><th>Window end</th><th>Type</th><th>Result</th><th>Score</th><th>Model</th><th>Created</th></tr>
            </thead>
            <tbody>
              <tr *ngFor="let prediction of predictionHistory">
                <td>{{ prediction.window_end | date:'medium' }}</td>
                <td>{{ prediction.prediction_type === 'FAILURE_PREDICTION' ? 'Failure risk' : 'Anomaly detection' }}</td>
                <td>{{ prediction.risk_level || (prediction.is_anomalous ? 'Anomalous' : 'Normal') }}</td>
                <td>{{ prediction.score | number:'1.3-3' }}</td>
                <td>{{ prediction.model.name }} <span class="text-muted">{{ prediction.model.version }}</span></td>
                <td>{{ prediction.created_at | date:'medium' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  `,
  styles: [`
    .drive-detail-page {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }

    .top-nav {
      .back-link {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        font-size: 0.85rem;
        font-weight: 500;
        color: var(--text-muted);
        &:hover { color: var(--primary); }
      }
    }

    .drive-header-card {
      padding: 1.5rem;

      .header-main {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        flex-wrap: wrap;

        .drive-identity {
          display: flex;
          align-items: center;
          gap: 1rem;

          .drive-icon {
            width: 48px;
            height: 48px;
            background: #f1f5f9;
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #334155;
          }

          .id-row {
            display: flex;
            align-items: center;
            gap: 0.75rem;

            .drive-title {
              font-size: 1.5rem;
              font-weight: 700;
              color: #0f172a;
            }
          }

          .specs-row {
            display: flex;
            gap: 1.25rem;
            font-size: 0.825rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
            strong { color: var(--text-main); }
          }
        }
      }

      .score-alert {
        margin-top: 1rem;
        padding: 0.75rem 1rem;
        border-radius: var(--radius-sm);
        font-size: 0.85rem;
        &.score-success {
          background: var(--success-bg);
          border: 1px solid var(--success-border);
          color: var(--success-text);
        }
        &.score-error {
          background: var(--danger-bg);
          border: 1px solid var(--danger-border);
          color: var(--danger-text);
        }
      }
    }

    .assessment-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 1.25rem;

      .assessment-card {
        .card-header {
          .subtext { font-size: 0.75rem; color: var(--text-muted); }
        }

        .score-stat {
          display: flex;
          align-items: center;
          gap: 1.25rem;
          margin-top: 0.5rem;

          .stat-number {
            font-size: 2.25rem;
            font-weight: 800;
            color: #0f172a;
            line-height: 1;
          }

          .stat-icon {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: #f1f5f9;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #64748b;

            &.anomaly-icon {
              background: var(--anomaly-bg);
              color: var(--anomaly);
            }
          }

          .stat-info {
            display: flex;
            flex-direction: column;
            gap: 0.2rem;

            strong {
              font-size: 0.875rem;
              color: var(--text-main);
            }

            .model-note {
              font-size: 0.75rem;
              color: var(--text-muted);
              line-height: 1.35;
            }
          }
        }
      }
    }

    .charts-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 1.5rem;

      .chart-card {
        .chart-subtitle {
          font-size: 0.775rem;
          color: var(--text-muted);
        }

        .canvas-wrapper {
          position: relative;
          height: 280px;
          width: 100%;
          margin-top: 0.5rem;
        }
      }
    }

    .metadata-card {
      .meta-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 1rem;

        .meta-item {
          display: flex;
          flex-direction: column;
          gap: 0.2rem;

          .meta-label {
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
          }

          .meta-val {
            font-size: 0.875rem;
            color: var(--text-main);
          }
        }
      }
    }

    .history-table-wrap { overflow-x: auto; }
    .history-table { width: 100%; border-collapse: collapse; font-size: 0.825rem; }
    .history-table th, .history-table td { padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--border-color); white-space: nowrap; }
    .history-table th { color: var(--text-muted); font-weight: 600; }

    .font-mono {
      font-family: ui-monospace, SFMono-Regular, monospace;
    }
  `],
})
export class DriveDetailComponent implements OnInit {
  @ViewChild('smartCanvas') smartCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('riskCanvas') riskCanvas!: ElementRef<HTMLCanvasElement>;

  private route = inject(ActivatedRoute);
  private driveService = inject(DriveService);
  private predictionService = inject(PredictionService);
  private authService = inject(AuthService);
  private changeDetector = inject(ChangeDetectorRef);

  readonly isITProOrSysAdmin = this.authService.isITProOrSysAdmin;

  driveId!: string;
  drive: DriveDetail | null = null;
  telemetryData: DriveTelemetryData | null = null;
  predictionHistory: DrivePredictionHistoryItem[] = [];
  historyLoading = true;
  historyError = false;
  scoring = false;
  scoreMessage = '';
  scoreError = false;

  private smartChart: Chart | null = null;
  private riskChart: Chart | null = null;

  ngOnInit(): void {
    this.driveId = this.route.snapshot.paramMap.get('id')!;
    this.loadData();
  }

  loadData(): void {
    this.driveService.getDrive(this.driveId).subscribe({
      next: (d) => {
        this.drive = d;
        this.changeDetector.markForCheck();
      },
    });

    this.driveService.getTelemetry(this.driveId, 90).subscribe({
      next: (data) => {
        this.telemetryData = data;
        this.changeDetector.markForCheck();
        setTimeout(() => this.renderCharts(), 50);
      },
    });

    this.historyLoading = true;
    this.historyError = false;
    this.driveService.getPredictionHistory(this.driveId).subscribe({
      next: (history) => {
        this.predictionHistory = history;
        this.historyLoading = false;
        this.changeDetector.markForCheck();
      },
      error: () => {
        this.historyLoading = false;
        this.historyError = true;
        this.changeDetector.markForCheck();
      },
    });
  }

  onScoreDrive(): void {
    this.scoring = true;
    this.scoreMessage = '';
    this.scoreError = false;

    this.predictionService.runPrediction(this.driveId).subscribe({
      next: (res) => {
        this.scoring = false;
        if (res.results.length > 0) {
          const item = res.results[0];
          this.scoreMessage = `Prediction successfully completed! Risk Score: ${item.risk_score.toFixed(3)} (${item.risk_level}), Anomaly: ${item.is_anomalous ? 'ANOMALOUS' : 'NORMAL'}.`;
          this.loadData();
        } else if (res.errors.length > 0) {
          this.scoreError = true;
          this.scoreMessage = `Prediction failed: ${res.errors[0].error}`;
        }
      },
      error: (err) => {
        this.scoring = false;
        this.scoreError = true;
        this.scoreMessage = `Inference request failed: ${err.error?.detail || err.message}`;
      },
    });
  }

  renderCharts(): void {
    if (!this.telemetryData) return;

    // Render SMART Chart
    if (this.smartCanvas && this.telemetryData.smart) {
      if (this.smartChart) this.smartChart.destroy();

      const labels = this.telemetryData.smart.labels;
      const datasets = (this.telemetryData.smart.series || []).map((s, idx) => {
        const colors = ['#2563eb', '#ef4444', '#f59e0b'];
        return {
          label: s.label,
          data: s.values,
          borderColor: colors[idx % colors.length],
          backgroundColor: colors[idx % colors.length],
          tension: 0.2,
          pointRadius: 2,
        };
      });

      this.smartChart = new Chart(this.smartCanvas.nativeElement, {
        type: 'line',
        data: { labels, datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'top', labels: { boxWidth: 12 } },
          },
          scales: {
            y: { beginAtZero: true, grid: { color: '#f1f5f9' } },
            x: { grid: { display: false } },
          },
        },
      });
    }

    // Render Risk Chart
    if (this.riskCanvas && this.telemetryData.risk) {
      if (this.riskChart) this.riskChart.destroy();

      const labels = this.telemetryData.risk.labels;
      const scores = this.telemetryData.risk.scores;
      const medThresh = this.telemetryData.thresholds?.medium ?? 0.35;
      const highThresh = this.telemetryData.thresholds?.high ?? 0.60;
      const critThresh = this.telemetryData.thresholds?.critical ?? 0.80;

      this.riskChart = new Chart(this.riskCanvas.nativeElement, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'Failure-Risk Score',
              data: scores,
              borderColor: '#6366f1',
              backgroundColor: 'rgba(99, 102, 241, 0.1)',
              fill: true,
              tension: 0.2,
              pointRadius: 3,
            },
            {
              label: `Critical Threshold (${critThresh})`,
              data: new Array(labels.length).fill(critThresh),
              borderColor: '#ef4444',
              borderDash: [5, 5],
              pointRadius: 0,
              fill: false,
            },
            {
              label: `High Threshold (${highThresh})`,
              data: new Array(labels.length).fill(highThresh),
              borderColor: '#f97316',
              borderDash: [5, 5],
              pointRadius: 0,
              fill: false,
            },
            {
              label: `Medium Threshold (${medThresh})`,
              data: new Array(labels.length).fill(medThresh),
              borderColor: '#facc15',
              borderDash: [5, 5],
              pointRadius: 0,
              fill: false,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'top', labels: { boxWidth: 12 } },
          },
          scales: {
            y: { min: 0, max: 1.0, grid: { color: '#f1f5f9' } },
            x: { grid: { display: false } },
          },
        },
      });
    }
  }

  formatCapacity(bytes?: number): string {
    if (!bytes) return '12 TB';
    const tb = bytes / (1024 * 1024 * 1024 * 1024);
    return `${tb.toFixed(1)} TB`;
  }
}
