import { ChangeDetectorRef, Component, Input, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { DriveService, DriveQueryParams } from '../../../core/services/drive.service';
import { Drive, PaginatedResponse } from '../../../core/models/drive.models';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-drive-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <div class="drives-page">
      <div class="page-header">
        <div>
          <h1 class="page-title">{{ highRiskOnly ? 'High-Risk Drives' : 'Drive Fleet Inventory' }}</h1>
          <p class="page-subtitle">
            {{ highRiskOnly
              ? 'Drives currently classified as high risk.'
              : 'Monitored disk storage units and individual predictive telemetry states.' }}
          </p>
        </div>
      </div>

      <!-- Filters & Search Toolbar -->
      <div class="card toolbar-card">
        <div class="search-box">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            type="text"
            [(ngModel)]="search"
            (ngModelChange)="onSearchChange()"
            placeholder="Search by serial number, model, or datacenter..."
            class="search-input"
          />
        </div>

        <div class="filters-group">
          <select *ngIf="!highRiskOnly" [(ngModel)]="statusFilter" (change)="loadDrives(1)" class="form-select filter-select">
            <option value="">All Statuses</option>
            <option value="HEALTHY">Healthy</option>
            <option value="WARNING">Warning</option>
            <option value="HIGH_RISK">High Risk</option>
          </select>

          <select [(ngModel)]="riskFilter" (change)="loadDrives(1)" class="form-select filter-select">
            <option value="">All Risk Levels</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
            <option value="NOT_SCORED">Not Scored</option>
          </select>

          <select [(ngModel)]="anomalyFilter" (change)="loadDrives(1)" class="form-select filter-select">
            <option value="">All Telemetry</option>
            <option value="true">Anomalous Only</option>
            <option value="false">Normal Only</option>
          </select>

          <select [(ngModel)]="ordering" (change)="loadDrives(1)" class="form-select filter-select">
            <option value="-risk_score">Highest Risk First</option>
            <option value="risk_score">Lowest Risk First</option>
            <option value="identifier">Serial (A-Z)</option>
            <option value="-identifier">Serial (Z-A)</option>
          </select>
        </div>
      </div>

      <!-- Drives Table -->
      <div class="card table-card">
        <div class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Drive Serial / ID</th>
                <th>Model</th>
                <th>Datacenter</th>
                <th>Status</th>
                <th>Failure Risk</th>
                <th>Risk Ranking Score</th>
                <th>Anomaly Status</th>
                <th>Scored Horizon</th>
                <th>Last Reading</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngIf="loading">
                <td colspan="10" class="text-center py-4">Loading drive inventory...</td>
              </tr>
              <tr *ngIf="!loading && loadError">
                <td colspan="10" class="text-center py-4" role="alert">
                  {{ loadError }}
                  <button type="button" class="btn btn-secondary btn-sm" (click)="loadDrives(currentPage)">Try again</button>
                </td>
              </tr>
              <tr *ngFor="let drive of drives">
                <td>
                  <a [routerLink]="['/drives', drive.id]" class="drive-link font-mono">
                    {{ drive.identifier }}
                  </a>
                </td>
                <td>
                  <div class="model-cell">
                    <span class="model-name">{{ drive.model || 'Unknown' }}</span>
                    <span class="vendor-sub text-muted">{{ drive.vendor }}</span>
                  </div>
                </td>
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
                  <span class="font-mono font-bold" *ngIf="drive.risk_score !== null">
                    {{ drive.risk_score | number:'1.3-3' }}
                  </span>
                  <span class="text-muted" *ngIf="drive.risk_score === null">—</span>
                </td>
                <td>
                  <span *ngIf="drive.anomaly_evaluated && drive.is_anomalous" class="badge badge-anomaly">
                    ANOMALOUS
                  </span>
                  <span *ngIf="drive.anomaly_evaluated && !drive.is_anomalous" class="badge badge-neutral">
                    NORMAL
                  </span>
                  <span *ngIf="!drive.anomaly_evaluated" class="badge badge-neutral">
                    NOT EVALUATED
                  </span>
                </td>
                <td class="text-muted">
                  {{ drive.scored_until ? (drive.scored_until | date:'yyyy-MM-dd') : '—' }}
                </td>
                <td class="text-muted">
                  {{ drive.last_reading ? (drive.last_reading | date:'yyyy-MM-dd') : '—' }}
                </td>
                <td>
                  <a [routerLink]="['/drives', drive.id]" class="btn btn-secondary btn-sm">
                    View
                  </a>
                </td>
              </tr>
              <tr *ngIf="!loading && !loadError && drives.length === 0">
                <td colspan="10" class="text-center py-4 text-muted">
                  {{ highRiskOnly ? 'No high-risk drives are currently available.' : 'No drives match the specified filters.' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div class="pagination-footer" *ngIf="totalCount > 0">
          <div class="pagination-info">
            Showing {{ (currentPage - 1) * pageSize + 1 }} - {{ min(currentPage * pageSize, totalCount) }} of {{ totalCount }} drives
          </div>
          <div class="pagination-controls">
            <button class="btn btn-secondary btn-sm" [disabled]="currentPage <= 1 || loading" (click)="loadDrives(currentPage - 1)">
              Previous
            </button>
            <span class="page-number">Page {{ currentPage }} of {{ totalPages() }}</span>
            <button class="btn btn-secondary btn-sm" [disabled]="currentPage >= totalPages() || loading" (click)="loadDrives(currentPage + 1)">
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .drives-page {
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
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

    .toolbar-card {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding: 0.85rem 1.25rem;
      flex-wrap: wrap;

      .search-box {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        flex: 1;
        min-width: 260px;
        background: #f8fafc;
        border: 1px solid var(--border-color);
        border-radius: var(--radius-sm);
        padding: 0.45rem 0.75rem;
        color: var(--text-muted);

        .search-input {
          border: none;
          background: transparent;
          width: 100%;
          font-size: 0.875rem;
          color: var(--text-main);
          &:focus { outline: none; }
        }
      }

      .filters-group {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        flex-wrap: wrap;

        .filter-select {
          padding: 0.45rem 0.65rem;
          font-size: 0.8rem;
          border-radius: var(--radius-sm);
          min-width: 130px;
        }
      }
    }

    .model-cell {
      display: flex;
      flex-direction: column;
      .model-name { font-weight: 500; }
      .vendor-sub { font-size: 0.725rem; }
    }

    .dc-chip {
      font-size: 0.75rem;
      padding: 0.15rem 0.4rem;
      background: #f1f5f9;
      border-radius: 4px;
      color: #475569;
    }

    .font-mono {
      font-family: ui-monospace, SFMono-Regular, monospace;
    }
    .font-bold { font-weight: 700; }

    .drive-link {
      color: var(--primary);
      &:hover { text-decoration: underline; }
    }

    .pagination-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding-top: 1rem;
      margin-top: 1rem;
      border-top: 1px solid var(--border-subtle);

      .pagination-info {
        font-size: 0.8rem;
        color: var(--text-muted);
      }

      .pagination-controls {
        display: flex;
        align-items: center;
        gap: 0.75rem;

        .page-number {
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--text-main);
        }
      }
    }
  `],
})
export class DriveListComponent implements OnInit {
  private driveService = inject(DriveService);
  private changeDetector = inject(ChangeDetectorRef);

  @Input() highRiskOnly = false;

  drives: Drive[] = [];
  loading = false;
  loadError = '';
  totalCount = 0;
  pageSize = 20;
  currentPage = 1;

  search = '';
  statusFilter = '';
  riskFilter = '';
  anomalyFilter = '';
  ordering = '-risk_score';

  private searchTimeout: any;

  ngOnInit(): void {
    if (this.highRiskOnly) {
      this.statusFilter = 'HIGH_RISK';
    }
    this.loadDrives(1);
  }

  onSearchChange(): void {
    clearTimeout(this.searchTimeout);
    this.searchTimeout = setTimeout(() => {
      this.loadDrives(1);
    }, 300);
  }

  loadDrives(page: number): void {
    this.currentPage = page;
    this.loading = true;
    this.loadError = '';

    const params: DriveQueryParams = {
      search: this.search,
      status: this.highRiskOnly ? 'HIGH_RISK' : this.statusFilter,
      risk_level: this.riskFilter,
      is_anomalous: this.anomalyFilter,
      ordering: this.ordering,
      page: this.currentPage,
      page_size: this.pageSize,
    };

    this.driveService.getDrives(params).subscribe({
      next: (resp) => {
        this.drives = resp.results;
        this.totalCount = resp.count;
        this.loading = false;
        this.changeDetector.markForCheck();
      },
      error: () => {
        this.loading = false;
        this.drives = [];
        this.loadError = 'Drive inventory could not be loaded.';
        this.changeDetector.markForCheck();
      },
    });
  }

  totalPages(): number {
    return Math.ceil(this.totalCount / this.pageSize) || 1;
  }

  min(a: number, b: number): number {
    return Math.min(a, b);
  }
}
