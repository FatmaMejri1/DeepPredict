import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TelemetryService } from '../../core/services/telemetry.service';
import { ValidationReport } from '../../core/models/telemetry.models';

@Component({
  selector: 'app-validation',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="validation-page">
      <div class="page-header">
        <div>
          <h1 class="page-title">Dataset Pre-Inference Validation</h1>
          <p class="page-subtitle">Verify SMART telemetry compliance against the AI model requirements prior to prediction.</p>
        </div>
      </div>

      <!-- Scenarios Runner -->
      <div class="card scenarios-card">
        <div class="card-header">
          <h3>Interactive Scenario Compliance Testing</h3>
          <span class="badge badge-neutral">Quick Scenarios</span>
        </div>
        <p class="scenarios-desc">
          Test DeepPredict's model validation engine against standard compliance benchmarks or upload your own telemetry file.
        </p>

        <div class="scenarios-buttons">
          <button class="btn btn-secondary btn-sm" (click)="runScenario('valid')" [disabled]="loading">
            Scenario 1: Valid 14-Day Sequence (Pass)
          </button>
          <button class="btn btn-secondary btn-sm" (click)="runScenario('short')" [disabled]="loading">
            Scenario 2: Insufficient History (&lt; 14 Days)
          </button>
          <button class="btn btn-secondary btn-sm" (click)="runScenario('gap')" [disabled]="loading">
            Scenario 3: Excessive Gap (&gt; 3 Days Missing)
          </button>
        </div>
      </div>

      <!-- Custom Upload for Validation -->
      <div class="card upload-val-card">
        <div class="card-header">
          <h3>Validate Custom Dataset File</h3>
        </div>
        <div class="file-pick-row">
          <input #fileInput type="file" (change)="onFileSelected($event)" accept=".csv, .json" class="file-input" />
          <button class="btn btn-primary" (click)="onValidateFile()" [disabled]="!selectedFile || loading">
            Run Complete Model Validation
          </button>
        </div>
      </div>

      <!-- Report Card -->
      <div class="card report-card" *ngIf="report">
        <div class="card-header">
          <div class="report-status-header">
            <h3>Compliance Verification Report</h3>
            <span class="badge" [class.badge-passed]="report.ready_for_prediction" [class.badge-error]="!report.ready_for_prediction">
              {{ report.ready_for_prediction ? 'READY FOR INFERENCE' : 'PREDICTION REJECTED' }}
            </span>
          </div>
          <span class="compatibility-badge" *ngIf="report.model_compatibility_verified">
            Drive Model Compatibility: <strong>VERIFIED</strong>
          </span>
        </div>

        <!-- Metrics Overview -->
        <div class="val-metrics-grid" *ngIf="report.metrics">
          <div class="val-metric">
            <span class="metric-label">TOTAL READINGS</span>
            <span class="metric-val">{{ report.metrics.total_readings }}</span>
          </div>
          <div class="val-metric">
            <span class="metric-label">CALENDAR DAYS</span>
            <span class="metric-val" [class.text-danger]="report.metrics.calendar_days < 14">{{ report.metrics.calendar_days }} / 14 min</span>
          </div>
          <div class="val-metric">
            <span class="metric-label">MISSING DAYS</span>
            <span class="metric-val">{{ report.metrics.missing_days || 0 }}</span>
          </div>
          <div class="val-metric">
            <span class="metric-label">SMART FEATURES</span>
            <span class="metric-val">{{ report.metrics.available_features }}</span>
          </div>
        </div>

        <!-- Checks List -->
        <div class="checks-section">
          <h4>Constraint Verification Checks</h4>
          <div class="checks-list">
            <div class="check-box" *ngFor="let check of report.checks" [class.check-error]="check.status === 'error'" [class.check-warning]="check.status === 'warning'" [class.check-passed]="check.status === 'passed'">
              <div class="check-header">
                <span class="badge" [class.badge-passed]="check.status === 'passed'" [class.badge-warning]="check.status === 'warning'" [class.badge-error]="check.status === 'error'">
                  {{ check.status }}
                </span>
                <span class="check-name">{{ check.name }}</span>
              </div>
              <p class="check-msg">{{ check.message }}</p>
            </div>
          </div>
        </div>

        <!-- Recommendations -->
        <div class="recommendations-section" *ngIf="report.recommendations?.length">
          <h4>Model Compliance Recommendations</h4>
          <ul class="rec-list">
            <li *ngFor="let rec of report.recommendations">{{ rec }}</li>
          </ul>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .validation-page {
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

    .scenarios-card {
      .scenarios-desc {
        font-size: 0.85rem;
        color: var(--text-muted);
        margin-bottom: 1rem;
      }
      .scenarios-buttons {
        display: flex;
        gap: 0.75rem;
        flex-wrap: wrap;
      }
    }

    .upload-val-card {
      .file-pick-row {
        display: flex;
        align-items: center;
        gap: 1rem;
        flex-wrap: wrap;

        .file-input {
          font-size: 0.85rem;
        }
      }
    }

    .report-card {
      .report-status-header {
        display: flex;
        align-items: center;
        gap: 1rem;
      }

      .compatibility-badge {
        font-size: 0.8rem;
        color: var(--text-muted);
        strong { color: #10b981; }
      }

      .val-metrics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 1rem;
        margin-bottom: 1.5rem;

        .val-metric {
          background: #f8fafc;
          border: 1px solid var(--border-color);
          border-radius: var(--radius-sm);
          padding: 0.75rem;
          display: flex;
          flex-direction: column;

          .metric-label {
            font-size: 0.65rem;
            font-weight: 700;
            color: var(--text-muted);
          }
          .metric-val {
            font-size: 1.25rem;
            font-weight: 700;
            color: #0f172a;
            &.text-danger { color: #ef4444; }
          }
        }
      }

      .checks-section {
        margin-bottom: 1.5rem;
        h4 {
          font-size: 0.95rem;
          margin-bottom: 0.75rem;
          color: #0f172a;
        }

        .checks-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;

          .check-box {
            padding: 0.75rem 1rem;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border-color);
            background: #ffffff;

            &.check-passed { border-left: 4px solid var(--success); }
            &.check-warning { border-left: 4px solid var(--warning); background: #fffbeb; }
            &.check-error { border-left: 4px solid var(--danger); background: #fef2f2; }

            .check-header {
              display: flex;
              align-items: center;
              gap: 0.5rem;
              margin-bottom: 0.25rem;

              .check-name {
                font-size: 0.825rem;
                font-weight: 600;
                color: var(--text-main);
              }
            }

            .check-msg {
              font-size: 0.8rem;
              color: var(--text-muted);
            }
          }
        }
      }

      .recommendations-section {
        background: #f8fafc;
        border: 1px solid var(--border-color);
        padding: 1rem;
        border-radius: var(--radius-sm);

        h4 {
          font-size: 0.875rem;
          color: #0f172a;
          margin-bottom: 0.5rem;
        }

        .rec-list {
          padding-left: 1.25rem;
          font-size: 0.8rem;
          color: var(--text-muted);
          line-height: 1.5;
        }
      }
    }
  `],
})
export class ValidationComponent {
  private telemetryService = inject(TelemetryService);

  loading = false;
  selectedFile: File | null = null;
  report: ValidationReport | null = null;

  onFileSelected(e: Event): void {
    const target = e.target as HTMLInputElement;
    if (target.files?.length) {
      this.selectedFile = target.files[0];
    }
  }

  onValidateFile(): void {
    if (!this.selectedFile) return;
    this.loading = true;
    this.telemetryService.validateFile(this.selectedFile).subscribe({
      next: (rep) => {
        this.report = rep;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
  }

  runScenario(type: 'valid' | 'short' | 'gap'): void {
    this.loading = true;
    const readings: any[] = [];
    const baseDate = new Date();
    baseDate.setDate(baseDate.getDate() - 20);

    const count = type === 'short' ? 6 : 14;

    for (let i = 0; i < count; i++) {
      const d = new Date(baseDate);
      // If gap scenario, simulate a 5-day missing gap after day 5
      const offset = (type === 'gap' && i >= 5) ? i + 6 : i;
      d.setDate(d.getDate() + offset);

      readings.push({
        serial_number: 'TEST-DISK',
        model: 'ST12000NM0007',
        date: d.toISOString().split('T')[0],
        smart_5_raw: 5,
        smart_9_raw: 9000,
        smart_187_raw: 0,
        smart_197_raw: 0,
      });
    }

    this.telemetryService.validateReadings(readings).subscribe({
      next: (rep) => {
        this.report = rep;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
  }
}
