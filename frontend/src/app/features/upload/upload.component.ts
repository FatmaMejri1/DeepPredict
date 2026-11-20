import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { TelemetryService } from '../../core/services/telemetry.service';
import { TelemetryUploadResponse, ValidationReport } from '../../core/models/telemetry.models';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <div class="upload-page">
      <div class="page-header">
        <div>
          <h1 class="page-title">Upload SMART Telemetry</h1>
          <p class="page-subtitle">Ingest telemetry batches into the monitored fleet storage repository.</p>
        </div>
      </div>

      <!-- Constraints Banner -->
      <div class="constraints-banner card">
        <div class="banner-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
        </div>
        <div class="banner-body">
          <h4>Required Model Ingestion Constraints</h4>
          <ul class="constraints-list">
            <li><strong>14 Calendar Days:</strong> The GRU and LSTM-AE models require at least 14 days of sequential telemetry.</li>
            <li><strong>22 SMART Features:</strong> Raw physical counters (e.g. <code>smart_5_raw</code>, <code>smart_187_raw</code>, <code>smart_197_raw</code>).</li>
            <li><strong>Max Gap of 3 Days:</strong> Forward filling is strictly limited to 3 consecutive missing days to maintain statistical validity.</li>
            <li><strong>Ranking Score:</strong> Failure forecasting generates a ranking score, NOT an absolute probability.</li>
          </ul>
        </div>
      </div>

      <!-- Upload Zone Card -->
      <div class="card upload-card">
        <div class="card-header">
          <h3>Dataset File Selection</h3>
          <span class="file-types-hint">Supported formats: CSV, JSON</span>
        </div>

        <div
          class="drop-zone"
          [class.dragover]="isDragging"
          (dragover)="onDragOver($event)"
          (dragleave)="onDragLeave($event)"
          (drop)="onDrop($event)"
          (click)="fileInput.click()"
        >
          <input
            #fileInput
            type="file"
            (change)="onFileSelected($event)"
            accept=".csv, .json"
            style="display: none"
          />
          <div class="drop-content">
            <div class="upload-icon">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>
              </svg>
            </div>
            <div class="upload-prompt" *ngIf="!selectedFile">
              <strong>Click to upload</strong> or drag and drop SMART telemetry dataset
              <span class="upload-hint">CSV with date, serial_number, model and SMART raw attributes</span>
            </div>
            <div class="file-selected" *ngIf="selectedFile">
              <span class="file-name font-mono">{{ selectedFile.name }}</span>
              <span class="file-size">{{ (selectedFile.size / 1024).toFixed(1) }} KB</span>
            </div>
          </div>
        </div>

        <div class="action-bar" *ngIf="selectedFile">
          <button class="btn btn-secondary" (click)="onValidate()" [disabled]="validating || uploading">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="m9 11 3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
            </svg>
            <span>{{ validating ? 'Validating Dataset...' : 'Pre-Validate Model Constraints' }}</span>
          </button>

          <button class="btn btn-primary" (click)="onUpload()" [disabled]="uploading || validating">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            <span>{{ uploading ? 'Ingesting into Database...' : 'Ingest Telemetry into Fleet' }}</span>
          </button>
        </div>
      </div>

      <!-- Quick Synthetic Test Ingest Card -->
      <div class="card demo-card">
        <div class="card-header">
          <h3>Quick Synthetic SMART Sequence Ingestion</h3>
          <span class="badge badge-neutral">Quick Test Generator</span>
        </div>
        <p class="demo-desc">
          Generate and ingest a 14-day SMART telemetry sequence for a simulated drive (<code>DEMO-DISK-01</code>) with high reallocated sector degradation.
        </p>
        <button class="btn btn-secondary btn-sm" (click)="onInjectSampleSequence()" [disabled]="uploading">
          Generate & Ingest 14-Day Sample Sequence
        </button>
      </div>

      <!-- Validation Report Display -->
      <div class="card validation-card" *ngIf="validationReport">
        <div class="card-header">
          <div class="val-header-title">
            <h3>Pre-Validation Results</h3>
            <span class="badge" [class.badge-passed]="validationReport.ready_for_prediction" [class.badge-warning]="!validationReport.ready_for_prediction">
              {{ validationReport.ready_for_prediction ? 'READY FOR PREDICTION' : 'CONSTRAINTS UNMET' }}
            </span>
          </div>
        </div>

        <div class="val-checks-list">
          <div class="val-check-item" *ngFor="let check of validationReport.checks">
            <span class="check-icon" [class.check-passed]="check.status === 'passed'" [class.check-error]="check.status === 'error'" [class.check-warning]="check.status === 'warning'">
              {{ check.status === 'passed' ? '✓' : '!' }}
            </span>
            <div class="check-details">
              <strong>{{ check.name }}</strong>
              <p>{{ check.message }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Upload Results Alert -->
      <div class="card result-card" *ngIf="uploadResult">
        <div class="result-header">
          <span class="result-badge badge badge-healthy">SUCCESSFULLY INGESTED</span>
          <h3>Ingestion Complete</h3>
        </div>
        <div class="result-body">
          <p><strong>{{ uploadResult.ingested_readings }}</strong> SMART telemetry readings saved to database.</p>
          <p *ngIf="uploadResult.drives_affected?.length">
            Affected drive units: <code *ngFor="let d of uploadResult.drives_affected" class="drive-chip">{{ d }}</code>
          </p>
        </div>
        <div class="result-footer">
          <a routerLink="/predictions" class="btn btn-primary btn-sm">Proceed to Predictions →</a>
        </div>
      </div>

      <div class="error-banner" *ngIf="errorMessage">
        {{ errorMessage }}
      </div>
    </div>
  `,
  styles: [`
    .upload-page {
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

    .constraints-banner {
      display: flex;
      gap: 1.25rem;
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      padding: 1.25rem;

      .banner-icon {
        color: #2563eb;
      }

      .banner-body {
        h4 {
          font-size: 0.95rem;
          font-weight: 600;
          color: #1e3a8a;
          margin-bottom: 0.5rem;
        }

        .constraints-list {
          list-style-type: none;
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 0.5rem;
          font-size: 0.8rem;
          color: #1e40af;

          code {
            background: #dbeafe;
            padding: 0.1rem 0.35rem;
            border-radius: 4px;
            font-family: ui-monospace, monospace;
          }
        }
      }
    }

    .upload-card {
      .file-types-hint {
        font-size: 0.75rem;
        color: var(--text-muted);
      }

      .drop-zone {
        border: 2px dashed #cbd5e1;
        border-radius: var(--radius-md);
        padding: 3rem 2rem;
        text-align: center;
        background: #f8fafc;
        cursor: pointer;
        transition: all 0.2s ease;

        &:hover, &.dragover {
          border-color: var(--primary);
          background: #eff6ff;
        }

        .drop-content {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.75rem;

          .upload-icon {
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: #ffffff;
            border: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--primary);
            box-shadow: var(--shadow-sm);
          }

          .upload-prompt {
            font-size: 0.95rem;
            color: var(--text-main);

            .upload-hint {
              display: block;
              font-size: 0.8rem;
              color: var(--text-muted);
              margin-top: 0.25rem;
            }
          }

          .file-selected {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            background: #ffffff;
            border: 1px solid var(--border-color);
            padding: 0.5rem 1rem;
            border-radius: var(--radius-sm);

            .file-name {
              font-weight: 600;
              color: var(--primary);
            }
            .file-size {
              font-size: 0.75rem;
              color: var(--text-muted);
            }
          }
        }
      }

      .action-bar {
        display: flex;
        justify-content: flex-end;
        gap: 0.75rem;
        margin-top: 1.25rem;
      }
    }

    .demo-card {
      .demo-desc {
        font-size: 0.85rem;
        color: var(--text-muted);
        margin-bottom: 1rem;
        line-height: 1.4;
      }
    }

    .validation-card {
      .val-header-title {
        display: flex;
        align-items: center;
        gap: 1rem;
      }

      .val-checks-list {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;

        .val-check-item {
          display: flex;
          align-items: flex-start;
          gap: 0.75rem;
          padding: 0.75rem;
          border-radius: var(--radius-sm);
          background: #f8fafc;
          border: 1px solid var(--border-color);

          .check-icon {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 0.8rem;

            &.check-passed { background: #d1fae5; color: #065f46; }
            &.check-warning { background: #fef3c7; color: #92400e; }
            &.check-error { background: #fee2e2; color: #991b1b; }
          }

          .check-details {
            font-size: 0.825rem;
            strong { color: var(--text-main); }
            p { color: var(--text-muted); margin-top: 0.15rem; }
          }
        }
      }
    }

    .result-card {
      border-left: 4px solid var(--success);

      .result-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.5rem;
      }

      .result-body {
        font-size: 0.875rem;
        color: var(--text-main);

        .drive-chip {
          display: inline-block;
          margin-left: 0.5rem;
          padding: 0.15rem 0.5rem;
          background: #f1f5f9;
          border-radius: 4px;
          font-family: ui-monospace, monospace;
          font-weight: 600;
        }
      }

      .result-footer {
        margin-top: 1rem;
      }
    }

    .error-banner {
      padding: 1rem;
      background: var(--danger-bg);
      border: 1px solid var(--danger-border);
      border-radius: var(--radius-sm);
      color: var(--danger-text);
      font-size: 0.875rem;
    }
  `],
})
export class UploadComponent {
  private telemetryService = inject(TelemetryService);

  selectedFile: File | null = null;
  isDragging = false;
  validating = false;
  uploading = false;
  validationReport: ValidationReport | null = null;
  uploadResult: TelemetryUploadResponse | null = null;
  errorMessage = '';

  onDragOver(e: DragEvent): void {
    e.preventDefault();
    this.isDragging = true;
  }

  onDragLeave(e: DragEvent): void {
    e.preventDefault();
    this.isDragging = false;
  }

  onDrop(e: DragEvent): void {
    e.preventDefault();
    this.isDragging = false;
    if (e.dataTransfer?.files?.length) {
      this.selectedFile = e.dataTransfer.files[0];
      this.validationReport = null;
      this.uploadResult = null;
      this.errorMessage = '';
    }
  }

  onFileSelected(e: Event): void {
    const target = e.target as HTMLInputElement;
    if (target.files?.length) {
      this.selectedFile = target.files[0];
      this.validationReport = null;
      this.uploadResult = null;
      this.errorMessage = '';
    }
  }

  onValidate(): void {
    if (!this.selectedFile) return;

    this.validating = true;
    this.errorMessage = '';
    this.telemetryService.validateFile(this.selectedFile).subscribe({
      next: (rep) => {
        this.validationReport = rep;
        this.validating = false;
      },
      error: (err) => {
        this.validating = false;
        this.errorMessage = `Validation error: ${err.error?.errors?.[0] || err.message}`;
      },
    });
  }

  onUpload(): void {
    if (!this.selectedFile) return;

    this.uploading = true;
    this.errorMessage = '';
    this.telemetryService.uploadFile(this.selectedFile).subscribe({
      next: (res) => {
        this.uploadResult = res;
        this.uploading = false;
      },
      error: (err) => {
        this.uploading = false;
        this.errorMessage = `Upload failed: ${err.error?.error || err.message}`;
      },
    });
  }

  onInjectSampleSequence(): void {
    this.uploading = true;
    this.errorMessage = '';
    this.uploadResult = null;

    // Generate 14 continuous daily readings for DEMO-DISK-01 with ascending reallocated sectors
    const readings = [];
    const baseDate = new Date();
    baseDate.setDate(baseDate.getDate() - 14);

    for (let i = 0; i < 14; i++) {
      const d = new Date(baseDate);
      d.setDate(d.getDate() + i);
      const dateStr = d.toISOString().split('T')[0];

      readings.push({
        serial_number: 'DEMO-DISK-01',
        model: 'ST12000NM0007',
        vendor: 'Seagate',
        datacenter: 'DC-1',
        date: dateStr,
        smart_5_raw: 10 + i * 5,
        smart_9_raw: 8000 + i * 24,
        smart_187_raw: i > 7 ? (i - 7) * 2 : 0,
        smart_197_raw: i > 10 ? (i - 10) * 3 : 0,
        smart_198_raw: 0,
      });
    }

    this.telemetryService.uploadReadings(readings).subscribe({
      next: (res) => {
        this.uploadResult = res;
        this.uploading = false;
      },
      error: (err) => {
        this.uploading = false;
        this.errorMessage = `Failed to generate sample sequence: ${err.error?.error || err.message}`;
      },
    });
  }
}
