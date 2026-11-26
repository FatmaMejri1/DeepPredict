import { ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { interval } from 'rxjs';
import { DashboardService } from '../../core/services/dashboard.service';
import { DashboardActivityItem, DashboardSummary } from '../../core/models/dashboard.models';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-overview',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="overview-page">
      <div class="page-header">
        <div>
          <h1 class="page-title">Fleet Health Overview</h1>
          <p class="page-subtitle">
            Predictive AI monitoring across production storage infrastructure.
            <span *ngIf="summary?.data_until" class="telemetry-timestamp">
              Telemetry recorded up to: <strong>{{ summary?.data_until | date:'mediumDate' }}</strong>
            </span>
          </p>
        </div>
        <div class="page-actions">
          <div class="refresh-control">
            <span class="last-updated" aria-live="polite">
              {{ lastUpdatedAt ? ('Last updated ' + (lastUpdatedAt | date:'medium')) : 'Waiting for dashboard data' }}
            </span>
            <button type="button" class="btn btn-secondary btn-sm" (click)="refreshDashboard()" [disabled]="refreshing" aria-label="Refresh dashboard">
              {{ refreshing ? 'Refreshing…' : 'Refresh' }}
            </button>
          </div>
          <div class="header-actions" *ngIf="isITProOrSysAdmin()">
            <a routerLink="/upload" class="btn btn-secondary btn-sm">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>
              </svg>
              Upload Telemetry
            </a>
            <a routerLink="/predictions" class="btn btn-primary btn-sm">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
              Run Inference
            </a>
          </div>
        </div>
      </div>

      <div *ngIf="summaryError" class="dashboard-state error-state" role="alert">
        <span>{{ summaryError }}</span>
        <button type="button" class="btn btn-secondary btn-sm" (click)="refreshDashboard()">Try again</button>
      </div>

      <div *ngIf="loading && !summary" class="dashboard-state loading-state" role="status">
        Loading fleet statistics…
      </div>

      <!-- KPI Grid -->
      <div class="kpi-grid" *ngIf="summary">
        <div class="kpi-card total">
          <div class="kpi-label">TOTAL MONITORED DRIVES</div>
          <div class="kpi-value">{{ summary.total }}</div>
          <div class="kpi-subtext">Active fleet storage units</div>
        </div>

        <div class="kpi-card healthy">
          <div class="kpi-label">HEALTHY</div>
          <div class="kpi-value">{{ summary.healthy }}</div>
          <div class="kpi-subtext">{{ percent(summary.healthy) }}% of total fleet</div>
        </div>

        <div class="kpi-card warning">
          <div class="kpi-label">WARNING</div>
          <div class="kpi-value">{{ summary.warning }}</div>
          <div class="kpi-subtext">Moderate wear / attention</div>
        </div>

        <div class="kpi-card high-risk">
          <div class="kpi-label">HIGH RISK / CRITICAL</div>
          <div class="kpi-value">{{ summary.high_risk }}</div>
          <div class="kpi-subtext">7-day failure horizon predicted</div>
        </div>

        <div class="kpi-card anomalous">
          <div class="kpi-label">ANOMALOUS DRIVES</div>
          <div class="kpi-value">{{ summary.anomalous }}</div>
          <div class="kpi-subtext">LSTM-AE telemetry deviation</div>
        </div>

        <div class="kpi-card not-scored">
          <div class="kpi-label">NOT SCORED</div>
          <div class="kpi-value">{{ summary.not_scored }}</div>
          <div class="kpi-subtext">&lt; 14-day history required</div>
        </div>
      </div>

      <div *ngIf="summary?.total === 0" class="dashboard-state empty-state">
        <strong>No drives are registered yet.</strong>
        <span>Import SMART telemetry to start monitoring your fleet.</span>
      </div>

      <!-- Fleet Distribution Bar -->
      <div class="card distribution-card" *ngIf="summary && summary.total > 0">
        <div class="card-header">
          <h3>Fleet Health Breakdown</h3>
          <span class="note-label">Based on calibrated decision thresholds</span>
        </div>
        <div class="distribution-bar">
          <div class="bar-segment healthy" [style.width.%]="(summary.healthy / summary.total) * 100" title="Healthy: {{ summary.healthy }}"></div>
          <div class="bar-segment warning" [style.width.%]="(summary.warning / summary.total) * 100" title="Warning: {{ summary.warning }}"></div>
          <div class="bar-segment high-risk" [style.width.%]="(summary.high_risk / summary.total) * 100" title="High Risk: {{ summary.high_risk }}"></div>
        </div>
        <div class="distribution-legend">
          <div class="legend-item"><span class="legend-dot healthy"></span> Healthy ({{ summary.healthy }})</div>
          <div class="legend-item"><span class="legend-dot warning"></span> Warning ({{ summary.warning }})</div>
          <div class="legend-item"><span class="legend-dot high-risk"></span> High Risk ({{ summary.high_risk }})</div>
          <div class="legend-item"><span class="legend-dot anomalous"></span> Anomalous Flagged ({{ summary.anomalous }})</div>
        </div>
      </div>

      <section class="card activity-card" aria-labelledby="activity-title">
        <div class="card-header activity-header">
          <div>
            <h3 id="activity-title">Recent analysis activity</h3>
            <p class="section-desc">Latest prediction results recorded for monitored drives.</p>
          </div>
          <span class="activity-count" *ngIf="activity.length">{{ activity.length }} latest</span>
        </div>

        <div *ngIf="activityLoading && !activity.length" class="activity-state" role="status">Loading recent activity…</div>
        <div *ngIf="activityError" class="activity-state error-text" role="alert">
          {{ activityError }}
          <button type="button" class="text-button" (click)="refreshDashboard()">Retry</button>
        </div>
        <div *ngIf="!activityLoading && !activityError && !activity.length" class="activity-state empty-activity">
          No prediction runs have been recorded yet.
        </div>

        <ol *ngIf="activity.length" class="activity-list">
          <li *ngFor="let item of activity">
            <span class="activity-marker" [class.anomaly-marker]="item.kind === 'Anomaly detection'" [class.risk-marker]="item.kind === 'Failure risk'"></span>
            <div class="activity-drive">
              <strong>{{ item.drive_identifier }}</strong>
              <span>{{ item.drive_name }}</span>
            </div>
            <div class="activity-result">
              <span class="activity-kind">{{ item.kind }}</span>
              <span class="badge" [class.badge-healthy]="item.outcome === 'LOW' || item.outcome === 'Normal'" [class.badge-warning]="item.outcome === 'MEDIUM'" [class.badge-high_risk]="item.outcome === 'HIGH' || item.outcome === 'CRITICAL'" [class.badge-anomaly]="item.outcome === 'Anomaly detected'">
                {{ item.outcome }}
              </span>
            </div>
            <time [attr.datetime]="item.created_at">{{ item.created_at | date:'medium' }}</time>
          </li>
        </ol>
      </section>

      <!-- Critical Drives Table -->
      <div class="card table-card">
        <div class="card-header">
          <div>
            <h3>Top At-Risk Drives</h3>
            <p class="section-desc">
              Drives ranked by failure-risk score. Note: The score is a relative ranking index, not an absolute probability.
            </p>
          </div>
          <a routerLink="/drives" class="btn btn-secondary btn-sm">View All {{ summary?.total }} Drives →</a>
        </div>

        <div class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Drive Serial / ID</th>
                <th>Model</th>
                <th>Datacenter</th>
                <th>Status</th>
                <th>Failure Risk Level</th>
                <th>Risk Ranking Score</th>
                <th>Anomaly Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let drive of summary?.top_critical">
                <td>
                  <a [routerLink]="['/drives', drive.id]" class="drive-link font-mono">
                    {{ drive.identifier }}
                  </a>
                </td>
                <td>{{ drive.model || 'Unknown' }}</td>
                <td><span class="dc-chip">{{ drive.datacenter || 'N/A' }}</span></td>
                <td>
                  <span class="badge" [class.badge-healthy]="drive.status === 'HEALTHY'" [class.badge-warning]="drive.status === 'WARNING'" [class.badge-high_risk]="drive.status === 'HIGH_RISK'">
                    {{ drive.status }}
                  </span>
                </td>
                <td>
                  <span class="badge"
                    [class.badge-low]="drive.risk_level === 'LOW'"
                    [class.badge-medium]="drive.risk_level === 'MEDIUM'"
                    [class.badge-high]="drive.risk_level === 'HIGH'"
                    [class.badge-critical]="drive.risk_level === 'CRITICAL'"
                    [class.badge-neutral]="!drive.risk_level">
                    {{ drive.risk_level || 'NOT SCORED' }}
                  </span>
                </td>
                <td>
                  <span class="risk-score-display" *ngIf="drive.risk_score !== null">
                    {{ drive.risk_score | number:'1.3-3' }}
                  </span>
                  <span class="text-muted" *ngIf="drive.risk_score === null">—</span>
                </td>
                <td>
                  <span *ngIf="drive.is_anomalous" class="badge badge-anomaly">
                    ANOMALOUS
                  </span>
                  <span *ngIf="!drive.is_anomalous" class="badge badge-neutral">
                    NORMAL
                  </span>
                </td>
                <td>
                  <a [routerLink]="['/drives', drive.id]" class="btn btn-secondary btn-sm">
                    Inspect
                  </a>
                </td>
              </tr>
              <tr *ngIf="summary?.total === 0">
                <td colspan="8" class="text-center py-4 text-muted">
                  No drives are available yet. Add drives or import telemetry to populate this overview.
                </td>
              </tr>
              <tr *ngIf="summary && summary.total > 0 && !summary.top_critical.length">
                <td colspan="8" class="text-center py-4 text-muted">
                  No drives have a stored failure-risk result yet.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .overview-page {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }

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

        .telemetry-timestamp {
          display: inline-block;
          margin-left: 0.5rem;
          padding: 0.15rem 0.5rem;
          background: #f1f5f9;
          border-radius: var(--radius-sm);
          font-size: 0.8rem;
          color: var(--text-main);
        }
      }

    }

    .page-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: 0.75rem;
    }

    .refresh-control {
      display: flex;
      align-items: center;
      gap: 0.65rem;

      .last-updated {
        color: var(--text-muted);
        font-size: 0.75rem;
        white-space: nowrap;
      }
    }

    .page-header .header-actions {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .dashboard-state {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding: 1rem 1.25rem;
      background: #ffffff;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      color: var(--text-main);
      font-size: 0.875rem;

      &.error-state {
        background: #fff7f7;
        border-color: #fecaca;
        color: #991b1b;
      }

      &.empty-state {
        align-items: flex-start;
        flex-direction: column;
        gap: 0.25rem;
      }
    }

    .kpi-grid .kpi-card {
      min-height: 126px;
      justify-content: center;
      gap: 0.15rem;
    }

    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 1rem;

      .kpi-card {
        background: #ffffff;
        border: 1px solid var(--border-color);
        border-radius: var(--radius-md);
        padding: 1.15rem;
        display: flex;
        flex-direction: column;
        border-top: 4px solid #cbd5e1;
        box-shadow: var(--shadow-sm);

        &.total { border-top-color: #2563eb; }
        &.healthy { border-top-color: #10b981; }
        &.warning { border-top-color: #f59e0b; }
        &.high-risk { border-top-color: #ef4444; }
        &.anomalous { border-top-color: #6366f1; }
        &.not-scored { border-top-color: #94a3b8; }

        .kpi-label {
          font-size: 0.7rem;
          font-weight: 700;
          color: var(--text-muted);
          letter-spacing: 0.05em;
          text-transform: uppercase;
        }

        .kpi-value {
          font-size: 2rem;
          font-weight: 700;
          color: #0f172a;
          margin: 0.25rem 0;
          line-height: 1;
        }

        .kpi-subtext {
          font-size: 0.75rem;
          color: var(--text-muted);
        }
      }
    }

    .distribution-card {
      .card-header {
        margin-bottom: 0.75rem;
        .note-label {
          font-size: 0.75rem;
          color: var(--text-muted);
        }
      }

      .distribution-bar {
        height: 14px;
        width: 100%;
        background: #f1f5f9;
        border-radius: 9999px;
        display: flex;
        overflow: hidden;
        margin-bottom: 1rem;

        .bar-segment {
          height: 100%;
          transition: width 0.3s ease;
          &.healthy { background: #10b981; }
          &.warning { background: #f59e0b; }
          &.high-risk { background: #ef4444; }
        }
      }

      .distribution-legend {
        display: flex;
        gap: 1.5rem;
        flex-wrap: wrap;

        .legend-item {
          display: flex;
          align-items: center;
          gap: 0.4rem;
          font-size: 0.8rem;
          color: var(--text-main);

          .legend-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            &.healthy { background: #10b981; }
            &.warning { background: #f59e0b; }
            &.high-risk { background: #ef4444; }
            &.anomalous { background: #6366f1; }
          }
        }
      }
    }

    .table-card {
      .section-desc {
        font-size: 0.8rem;
        color: var(--text-muted);
        margin-top: 0.25rem;
      }

      .font-mono {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-weight: 600;
      }

      .drive-link {
        color: var(--primary);
        &:hover { text-decoration: underline; }
      }

      .dc-chip {
        font-size: 0.75rem;
        padding: 0.15rem 0.4rem;
        background: #f1f5f9;
        border-radius: 4px;
        color: #475569;
      }

      .risk-score-display {
        font-weight: 700;
        font-family: ui-monospace, SFMono-Regular, monospace;
      }
    }

    .activity-card {
      .activity-header {
        margin-bottom: 0.5rem;
      }

      .section-desc {
        margin-top: 0.25rem;
        color: var(--text-muted);
        font-size: 0.8rem;
      }

      .activity-count {
        color: var(--text-muted);
        font-size: 0.75rem;
      }

      .activity-state {
        padding: 1rem 0.25rem;
        color: var(--text-muted);
        font-size: 0.85rem;
      }

      .error-text { color: #b91c1c; }

      .text-button {
        margin-left: 0.5rem;
        color: var(--primary);
        text-decoration: underline;
      }

      .activity-list {
        display: flex;
        flex-direction: column;
        margin: 0;
        padding: 0;
        list-style: none;

        li {
          display: grid;
          grid-template-columns: 12px minmax(130px, 1.1fr) minmax(160px, 1fr) minmax(150px, auto);
          align-items: center;
          gap: 0.85rem;
          min-height: 60px;
          border-top: 1px solid #eef2f7;
        }

        time {
          justify-self: end;
          color: var(--text-muted);
          font-size: 0.75rem;
        }
      }

      .activity-marker {
        width: 9px;
        height: 9px;
        border-radius: 50%;
        background: #f59e0b;
        &.anomaly-marker { background: #6366f1; }
        &.risk-marker { background: #ef4444; }
      }

      .activity-drive, .activity-result {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.45rem;
      }

      .activity-drive {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.1rem;
        min-width: 0;
        strong { color: #0f172a; font-size: 0.85rem; }
        span { color: var(--text-muted); font-size: 0.75rem; }
      }

      .activity-kind { color: var(--text-muted); font-size: 0.75rem; }
    }

    @media (max-width: 900px) {
      .page-header { flex-direction: column; }
      .page-actions { width: 100%; justify-content: space-between; }
      .kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    }

    @media (max-width: 620px) {
      .page-actions { align-items: flex-start; flex-direction: column; }
      .refresh-control { width: 100%; justify-content: space-between; }
      .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .activity-card .activity-list li {
        grid-template-columns: 12px minmax(0, 1fr) auto;
        padding: 0.65rem 0;
      }
      .activity-card .activity-result { grid-column: 2; }
      .activity-card .activity-list time { grid-column: 3; grid-row: 1 / span 2; }
    }
  `],
})
export class OverviewComponent implements OnInit {
  private dashboardService = inject(DashboardService);
  private authService = inject(AuthService);
  private changeDetector = inject(ChangeDetectorRef);
  private destroyRef = inject(DestroyRef);

  readonly isITProOrSysAdmin = this.authService.isITProOrSysAdmin;

  summary: DashboardSummary | null = null;
  loading = true;
  refreshing = false;
  summaryError = '';
  activity: DashboardActivityItem[] = [];
  activityLoading = true;
  activityError = '';
  lastUpdatedAt: Date | null = null;

  ngOnInit(): void {
    this.refreshDashboard();
    interval(60_000)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.refreshDashboard());
  }

  refreshDashboard(): void {
    if (this.refreshing) return;

    this.refreshing = true;
    this.loading = !this.summary;
    this.activityLoading = !this.activity.length;
    this.summaryError = '';
    this.activityError = '';
    let requestsRemaining = 2;
    const finishRequest = () => {
      requestsRemaining -= 1;
      if (requestsRemaining === 0) {
        this.refreshing = false;
        this.changeDetector.markForCheck();
      }
    };

    this.dashboardService.getSummary().subscribe({
      next: (data) => {
        this.summary = data;
        this.loading = false;
        this.lastUpdatedAt = new Date();
        finishRequest();
        this.changeDetector.markForCheck();
      },
      error: () => {
        this.loading = false;
        this.summaryError = 'Dashboard statistics could not be loaded.';
        finishRequest();
        this.changeDetector.markForCheck();
      },
    });

    this.dashboardService.getRecentActivity().subscribe({
      next: (data) => {
        this.activity = data.results;
        this.activityLoading = false;
        finishRequest();
        this.changeDetector.markForCheck();
      },
      error: () => {
        this.activityLoading = false;
        this.activityError = 'Recent activity could not be loaded.';
        finishRequest();
        this.changeDetector.markForCheck();
      },
    });
  }

  percent(val: number): string {
    if (!this.summary || this.summary.total === 0) return '0';
    return ((val / this.summary.total) * 100).toFixed(1);
  }
}
