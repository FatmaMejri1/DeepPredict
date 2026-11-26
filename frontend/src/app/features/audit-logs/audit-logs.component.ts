import { ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AuditAction, AuditLogFilters, AuditLogPage } from '../../core/models/audit-log.models';
import { AuditLogService } from '../../core/services/audit-log.service';

@Component({
  selector: 'app-audit-logs',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="audit-page" aria-labelledby="audit-title">
      <header class="page-heading">
        <div>
          <p class="eyebrow">SYSADMIN</p>
          <h1 id="audit-title">Audit Logs</h1>
          <p class="page-subtitle">Review recorded account, configuration, and monitoring events.</p>
        </div>
      </header>

      <form class="card filter-card" (ngSubmit)="applyFilters()" aria-label="Filter audit logs">
        <label>Username
          <input name="username" [(ngModel)]="filters.username" autocomplete="off" placeholder="Search actor username" />
        </label>
        <label>Action
          <select name="action" [(ngModel)]="filters.action">
            <option value="">All actions</option>
            <option *ngFor="let action of actions" [value]="action">{{ actionLabel(action) }}</option>
          </select>
        </label>
        <label>From date
          <input name="dateFrom" type="date" [(ngModel)]="filters.date_from" />
        </label>
        <label>To date
          <input name="dateTo" type="date" [(ngModel)]="filters.date_to" />
        </label>
        <div class="filter-actions">
          <button class="btn btn-primary" type="submit" [disabled]="loading">Apply</button>
          <button class="btn btn-secondary" type="button" (click)="clearFilters()" [disabled]="loading">Clear</button>
        </div>
      </form>

      <div *ngIf="loading" class="state-card" role="status" aria-live="polite">Loading audit records…</div>
      <div *ngIf="error" class="state-card error-state" role="alert">
        <span>{{ error }}</span>
        <button class="btn btn-secondary btn-sm" type="button" (click)="loadLogs()">Try again</button>
      </div>
      <div *ngIf="!loading && !error && page?.results?.length === 0" class="state-card empty-state" role="status">
        <h2>No audit records found</h2>
        <p>{{ hasFilters ? 'No records match the selected filters.' : 'There are no audit records available.' }}</p>
      </div>

      <section *ngIf="!loading && !error && page && page.results.length > 0" class="card table-card" aria-label="Audit log results">
        <div class="table-heading">{{ page.count }} record{{ page.count === 1 ? '' : 's' }}</div>
        <div class="table-scroll">
          <table>
            <thead><tr>
              <th scope="col">Timestamp</th><th scope="col">Actor</th><th scope="col">Action</th>
              <th scope="col">Resource type</th><th scope="col">Resource ID</th>
            </tr></thead>
            <tbody>
              <tr *ngFor="let entry of page.results">
                <td>{{ entry.timestamp | date:'medium' }}</td>
                <td>{{ entry.username || 'Unknown' }}</td>
                <td><span class="action-badge">{{ actionLabel(entry.action) }}</span></td>
                <td>{{ entry.resource_type || '—' }}</td>
                <td class="resource-id">{{ entry.resource_id || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <nav *ngIf="page.count > pageSize" class="pagination" aria-label="Audit log pages">
          <button class="btn btn-secondary btn-sm" type="button" (click)="loadLogs(currentPage - 1)" [disabled]="loading || !page.previous">Previous</button>
          <span>Page {{ currentPage }} of {{ totalPages }}</span>
          <button class="btn btn-secondary btn-sm" type="button" (click)="loadLogs(currentPage + 1)" [disabled]="loading || !page.next">Next</button>
        </nav>
      </section>
    </section>
  `,
  styles: [`
    .audit-page { display: flex; flex-direction: column; gap: 1.25rem; color: var(--text-main); }
    .page-heading { display: flex; justify-content: space-between; align-items: center; }
    .eyebrow { margin: 0 0 .25rem; color: var(--text-muted); font-size: .68rem; font-weight: 700; letter-spacing: .08em; }
    h1 { margin: 0; font-size: 1.65rem; }
    .page-subtitle { margin: .35rem 0 0; color: var(--text-muted); }
    .filter-card { display: flex; align-items: end; flex-wrap: wrap; gap: .8rem; padding: 1rem; }
    label { display: flex; flex: 1 1 150px; flex-direction: column; gap: .35rem; color: var(--text-muted); font-size: .78rem; font-weight: 600; }
    input, select { min-height: 38px; padding: .45rem .6rem; border: 1px solid var(--border-color); border-radius: var(--radius-sm); background: white; color: var(--text-main); font: inherit; }
    .filter-actions { display: flex; gap: .5rem; }
    .state-card { padding: 1.4rem; border: 1px solid var(--border-color); border-radius: var(--radius-md); background: white; }
    .error-state { display: flex; justify-content: space-between; align-items: center; gap: 1rem; color: #991b1b; }
    .empty-state { text-align: center; color: var(--text-muted); }
    .empty-state h2 { color: var(--text-main); font-size: 1.1rem; }
    .table-card { padding: 1rem; }
    .table-heading { margin-bottom: .75rem; color: var(--text-muted); font-size: .82rem; }
    .table-scroll { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: .84rem; }
    th, td { padding: .75rem .65rem; border-bottom: 1px solid var(--border-color); text-align: left; }
    th { color: var(--text-muted); font-size: .72rem; font-weight: 700; text-transform: uppercase; white-space: nowrap; }
    .resource-id { overflow-wrap: anywhere; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .action-badge { display: inline-flex; padding: .2rem .55rem; border-radius: 999px; background: #eff6ff; color: #1d4ed8; font-size: .72rem; font-weight: 700; white-space: nowrap; }
    .pagination { display: flex; justify-content: center; align-items: center; gap: 1rem; padding-top: 1rem; }
    @media (max-width: 700px) { .filter-card { align-items: stretch; flex-direction: column; } label { flex-basis: auto; } input, select { width: 100%; } .filter-actions { flex-wrap: wrap; } .error-state { align-items: flex-start; flex-direction: column; } }
  `],
})
export class AuditLogsComponent implements OnInit {
  private service = inject(AuditLogService);
  private changeDetector = inject(ChangeDetectorRef);
  private destroyRef = inject(DestroyRef);

  readonly pageSize = 25;
  readonly actions: AuditAction[] = [
    'LOGIN_SUCCESS', 'LOGIN_FAILED', 'LOGOUT', 'CREATE', 'UPDATE', 'DELETE',
    'PREDICT_RUN', 'CONFIG_CHANGE', 'TELEMETRY_UPLOAD',
  ];
  private readonly actionLabels: Record<AuditAction, string> = {
    LOGIN_SUCCESS: 'Login Successful',
    LOGIN_FAILED: 'Login Failed',
    LOGOUT: 'Logout',
    CREATE: 'Entity Created',
    UPDATE: 'Entity Updated',
    DELETE: 'Entity Deleted',
    PREDICT_RUN: 'Inference Executed',
    CONFIG_CHANGE: 'Configuration Changed',
    TELEMETRY_UPLOAD: 'Telemetry Uploaded',
  };
  filters: AuditLogFilters = { username: '', action: '', date_from: '', date_to: '' };
  page: AuditLogPage | null = null;
  currentPage = 1;
  loading = false;
  error = '';
  private requestSequence = 0;

  get hasFilters(): boolean {
    return Boolean(this.filters.username?.trim() || this.filters.action || this.filters.date_from || this.filters.date_to);
  }

  get totalPages(): number {
    return Math.max(1, Math.ceil((this.page?.count ?? 0) / this.pageSize));
  }

  ngOnInit(): void {
    this.loadLogs(1);
  }

  loadLogs(page = this.currentPage): void {
    const sequence = ++this.requestSequence;
    this.currentPage = Math.max(1, page);
    this.loading = true;
    this.error = '';
    this.page = null;
    this.service.getAuditLogs({ ...this.filters }, this.currentPage, this.pageSize)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          if (sequence !== this.requestSequence) return;
          this.page = result;
          this.loading = false;
          this.changeDetector.markForCheck();
        },
        error: () => {
          if (sequence !== this.requestSequence) return;
          this.loading = false;
          this.error = 'Audit records could not be loaded. Check your connection and try again.';
          this.changeDetector.markForCheck();
        },
      });
  }

  applyFilters(): void {
    this.loadLogs(1);
  }

  clearFilters(): void {
    this.filters = { username: '', action: '', date_from: '', date_to: '' };
    this.loadLogs(1);
  }

  actionLabel(action: AuditAction): string {
    return this.actionLabels[action];
  }
}
