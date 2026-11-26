import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { AlertFilters, AlertPage, AlertStatus, AlertType, AlertSeverity } from '../../../core/models/alert.models';
import { AlertService } from '../../../core/services/alert.service';

@Component({
  selector: 'app-alerts-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <section class="alerts-page" aria-labelledby="alerts-title">
      <header class="page-heading">
        <div>
          <p class="eyebrow">FLEET MONITORING</p>
          <h1 id="alerts-title">Alerts</h1>
          <p class="page-subtitle">Review persistent risk and anomaly events across your drives.</p>
        </div>
      </header>

      <section class="filter-card card" aria-label="Filter alerts">
        <div class="filters">
          <label>Status
            <select [(ngModel)]="filters.status" aria-label="Filter by alert status">
              <option value="">All statuses</option>
              <option value="OPEN">Open</option>
              <option value="ACKNOWLEDGED">Acknowledged</option>
              <option value="RESOLVED">Resolved</option>
            </select>
          </label>
          <label>Alert type
            <select [(ngModel)]="filters.alert_type" aria-label="Filter by alert type">
              <option value="">All types</option>
              <option value="FAILURE_RISK">Failure risk</option>
              <option value="ANOMALY">Anomaly</option>
            </select>
          </label>
          <label>Severity
            <select [(ngModel)]="filters.severity" aria-label="Filter by severity">
              <option value="">All severities</option>
              <option value="HIGH">High</option>
              <option value="CRITICAL">Critical</option>
            </select>
          </label>
          <label class="resource-filter">Resource UUID
            <input [(ngModel)]="filters.resource" aria-label="Filter by resource UUID" placeholder="Paste resource UUID" />
          </label>
          <div class="filter-actions">
            <button class="btn btn-primary" type="button" (click)="applyFilters()" [disabled]="loading">Apply</button>
            <button class="btn btn-secondary" type="button" (click)="clearFilters()" [disabled]="loading">Clear filters</button>
          </div>
        </div>
      </section>

      <div *ngIf="loading" class="state-card loading-state" role="status">Loading alerts…</div>
      <div *ngIf="error" class="state-card error-state" role="alert">
        <span>{{ error }}</span>
        <button class="btn btn-secondary btn-sm" type="button" (click)="loadAlerts()">Try again</button>
      </div>
      <div *ngIf="!loading && !error && page?.results?.length === 0" class="state-card empty-state">
        <h2>No alerts found</h2>
        <p>{{ hasFilters ? 'No alerts match these filters.' : 'There are no alert records yet.' }}</p>
        <button *ngIf="hasFilters" class="btn btn-secondary" type="button" (click)="clearFilters()">Clear filters</button>
      </div>

      <section *ngIf="!loading && !error && page && page.results.length > 0" class="card table-card" aria-label="Alert results">
        <div class="table-heading"><span>{{ page.count }} alert{{ page.count === 1 ? '' : 's' }}</span></div>
        <div class="table-scroll">
          <table>
            <thead><tr>
              <th scope="col">Alert</th><th scope="col">Resource</th><th scope="col">Severity</th>
              <th scope="col">First seen</th><th scope="col">Last seen</th><th scope="col">Occurrences</th><th scope="col">Details</th>
            </tr></thead>
            <tbody>
              <tr *ngFor="let alert of page.results">
                <td>
                  <span class="type-label" [class.type-risk]="alert.alert_type === 'FAILURE_RISK'" [class.type-anomaly]="alert.alert_type === 'ANOMALY'">
                    {{ alert.alert_type === 'FAILURE_RISK' ? 'Failure risk' : 'Anomaly' }}
                  </span>
                  <span class="status-badge" [ngClass]="'status-' + alert.status.toLowerCase()">{{ alert.status }}</span>
                </td>
                <td><a [routerLink]="['/drives', alert.resource.id]" class="resource-link">{{ alert.resource.name }}</a><small>{{ alert.resource.identifier }}</small></td>
                <td><span class="severity" [ngClass]="'severity-' + alert.severity.toLowerCase()">{{ alert.severity }}</span></td>
                <td>{{ alert.first_seen_at | date:'medium' }}</td>
                <td>{{ alert.last_seen_at | date:'medium' }}</td>
                <td>{{ alert.occurrence_count }}</td>
                <td><a class="btn btn-secondary btn-sm" [routerLink]="['/alerts', alert.id]">View alert</a></td>
              </tr>
            </tbody>
          </table>
        </div>
        <nav class="pagination" aria-label="Alert pages">
          <button class="btn btn-secondary btn-sm" type="button" (click)="loadAlerts(currentPage - 1)" [disabled]="loading || !page.previous">Previous</button>
          <span>Page {{ currentPage }} of {{ totalPages }}</span>
          <button class="btn btn-secondary btn-sm" type="button" (click)="loadAlerts(currentPage + 1)" [disabled]="loading || !page.next">Next</button>
        </nav>
      </section>
    </section>
  `,
  styles: [`
    .alerts-page { display: flex; flex-direction: column; gap: 1.25rem; color: var(--text-main); }
    .page-heading { display: flex; justify-content: space-between; align-items: center; }
    .eyebrow { margin: 0 0 .25rem; color: var(--text-muted); font-size: .68rem; font-weight: 700; letter-spacing: .08em; }
    h1 { margin: 0; font-size: 1.65rem; }
    .page-subtitle { margin: .35rem 0 0; color: var(--text-muted); }
    .filter-card, .table-card { padding: 1rem; }
    .filters { display: flex; flex-wrap: wrap; align-items: end; gap: .8rem; }
    label { display: flex; flex-direction: column; gap: .35rem; color: var(--text-muted); font-size: .78rem; font-weight: 600; }
    select, input { min-width: 145px; min-height: 38px; padding: .45rem .6rem; border: 1px solid var(--border-color); border-radius: var(--radius-sm); background: white; color: var(--text-main); font: inherit; }
    .resource-filter input { min-width: 220px; }
    .filter-actions { display: flex; gap: .5rem; }
    .state-card { padding: 1.4rem; border: 1px solid var(--border-color); border-radius: var(--radius-md); background: white; }
    .error-state { display: flex; justify-content: space-between; align-items: center; gap: 1rem; color: #991b1b; }
    .empty-state { text-align: center; color: var(--text-muted); }
    .empty-state h2 { color: var(--text-main); font-size: 1.1rem; }
    .table-heading { margin-bottom: .75rem; color: var(--text-muted); font-size: .82rem; }
    .table-scroll { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: .84rem; }
    th, td { padding: .75rem .65rem; border-bottom: 1px solid var(--border-color); text-align: left; white-space: nowrap; }
    th { color: var(--text-muted); font-size: .72rem; font-weight: 700; text-transform: uppercase; }
    td small { display: block; margin-top: .2rem; color: var(--text-muted); }
    .type-label, .status-badge, .severity { display: inline-flex; align-items: center; border-radius: 999px; padding: .2rem .5rem; font-size: .7rem; font-weight: 700; }
    .type-label { margin-right: .35rem; }
    .type-risk { color: #7c2d12; background: #ffedd5; }
    .type-anomaly { color: #5b21b6; background: #ede9fe; }
    .status-open { color: #991b1b; background: #fee2e2; }
    .status-acknowledged { color: #854d0e; background: #fef3c7; }
    .status-resolved { color: #166534; background: #dcfce7; }
    .severity-high { color: #9a3412; background: #ffedd5; }
    .severity-critical { color: #991b1b; background: #fee2e2; }
    .resource-link { color: var(--primary); font-weight: 600; text-decoration: none; }
    .resource-link:hover { text-decoration: underline; }
    .pagination { display: flex; justify-content: center; align-items: center; gap: 1rem; padding-top: 1rem; }
    @media (max-width: 700px) { .filters { align-items: stretch; flex-direction: column; } select, input { width: 100%; } .filter-actions { flex-wrap: wrap; } .error-state { align-items: flex-start; flex-direction: column; } }
  `],
})
export class AlertsListComponent {
  private alertService = inject(AlertService);
  private changeDetector = inject(ChangeDetectorRef);
  filters: AlertFilters = { status: '', alert_type: '', severity: '', resource: '' };
  page: AlertPage | null = null;
  currentPage = 1;
  readonly pageSize = 20;
  loading = false;
  error = '';
  private requestSequence = 0;

  get hasFilters(): boolean {
    return !!(this.filters.status || this.filters.alert_type || this.filters.severity || this.filters.resource?.trim());
  }

  get totalPages(): number {
    return Math.max(1, Math.ceil((this.page?.count ?? 0) / this.pageSize));
  }

  ngOnInit(): void {
    this.loadAlerts(1);
  }

  loadAlerts(page = this.currentPage): void {
    const sequence = ++this.requestSequence;
    this.currentPage = Math.max(1, page);
    this.loading = true;
    this.error = '';
    this.page = null;
    this.alertService.getAlerts(this.filters, this.currentPage, this.pageSize).subscribe({
      next: (result) => {
        if (sequence !== this.requestSequence) return;
        this.page = result;
        this.loading = false;
        this.changeDetector.markForCheck();
      },
      error: () => {
        if (sequence !== this.requestSequence) return;
        this.loading = false;
        this.error = 'Alerts could not be loaded. Check your filters or connection and try again.';
        this.changeDetector.markForCheck();
      },
    });
  }

  applyFilters(): void { this.loadAlerts(1); }

  clearFilters(): void {
    this.filters = { status: '', alert_type: '', severity: '', resource: '' };
    this.loadAlerts(1);
  }
}
