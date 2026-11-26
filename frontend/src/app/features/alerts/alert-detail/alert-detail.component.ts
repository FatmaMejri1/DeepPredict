import { ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Alert } from '../../../core/models/alert.models';
import { AlertService } from '../../../core/services/alert.service';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-alert-detail',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <section class="alert-detail-page" aria-labelledby="alert-detail-title">
      <a routerLink="/alerts" class="back-link">← Back to alerts</a>
      <div *ngIf="loading" class="state-card" role="status">Loading alert…</div>
      <div *ngIf="loadError" class="state-card error-state" role="alert">
        <span>{{ loadError }}</span>
        <button type="button" class="btn btn-secondary btn-sm" (click)="loadAlert()">Try again</button>
      </div>
      <p *ngIf="actionError" class="state-card error-state" role="alert">{{ actionError }}</p>

      <ng-container *ngIf="alert as current">
        <header class="detail-heading card">
          <div>
            <p class="eyebrow">ALERT DETAIL</p>
            <h1 id="alert-detail-title">{{ current.alert_type === 'FAILURE_RISK' ? 'Failure risk alert' : 'Anomaly alert' }}</h1>
            <div class="badges">
              <span class="severity" [ngClass]="'severity-' + current.severity.toLowerCase()">{{ current.severity }}</span>
              <span class="status-badge" [ngClass]="'status-' + current.status.toLowerCase()">{{ current.status }}</span>
            </div>
          </div>
          <div class="actions" *ngIf="canManage()">
            <button *ngIf="current.status === 'OPEN'" class="btn btn-secondary" type="button" (click)="acknowledge()" [disabled]="!!actionInProgress">
              {{ actionInProgress === 'acknowledge' ? 'Acknowledging…' : 'Acknowledge' }}
            </button>
            <button *ngIf="current.status !== 'RESOLVED'" class="btn btn-primary" type="button" (click)="resolve()" [disabled]="!!actionInProgress">
              {{ actionInProgress === 'resolve' ? 'Resolving…' : 'Resolve alert' }}
            </button>
          </div>
        </header>

        <div class="detail-grid">
          <section class="card information-card" aria-labelledby="event-info-title">
            <h2 id="event-info-title">Alert information</h2>
            <dl>
              <div><dt>Type</dt><dd>{{ current.alert_type === 'FAILURE_RISK' ? 'Failure risk' : 'Anomaly' }}</dd></div>
              <div><dt>Severity</dt><dd>{{ current.severity }}</dd></div>
              <div><dt>Status</dt><dd>{{ current.status }}</dd></div>
              <div><dt>First seen</dt><dd>{{ current.first_seen_at | date:'medium' }}</dd></div>
              <div><dt>Last seen</dt><dd>{{ current.last_seen_at | date:'medium' }}</dd></div>
              <div><dt>Occurrences</dt><dd>{{ current.occurrence_count }}</dd></div>
            </dl>
          </section>

          <section class="card information-card" aria-labelledby="resource-title">
            <h2 id="resource-title">Resource</h2>
            <p class="resource-name">{{ current.resource.name }}</p>
            <p class="resource-identifier">{{ current.resource.identifier }}</p>
            <p>{{ current.resource.resource_type }} · {{ current.resource.status }}</p>
            <a class="btn btn-secondary" [routerLink]="['/drives', current.resource.id]">Open drive details</a>
          </section>

          <section class="card information-card" aria-labelledby="prediction-title">
            <h2 id="prediction-title">Latest prediction context</h2>
            <ng-container *ngIf="current.latest_prediction as prediction; else noPrediction">
              <dl>
                <div><dt>Prediction type</dt><dd>{{ prediction.model_type }}</dd></div>
                <div><dt>Score</dt><dd>{{ prediction.score | number:'1.3-4' }}</dd></div>
                <div><dt>Risk level</dt><dd>{{ prediction.risk_level || 'Not applicable' }}</dd></div>
                <div><dt>Anomaly result</dt><dd>{{ prediction.is_anomalous === null ? 'Not applicable' : (prediction.is_anomalous ? 'Anomalous' : 'Normal') }}</dd></div>
                <div><dt>Model</dt><dd>{{ prediction.model.name }} · {{ prediction.model.version }} ({{ prediction.model.architecture }})</dd></div>
                <div><dt>Prediction window</dt><dd>{{ prediction.window_start | date:'mediumDate' }} – {{ prediction.window_end | date:'mediumDate' }}</dd></div>
              </dl>
              <p class="note">This shows the stored prediction result and model context; it does not attribute the result to individual SMART readings.</p>
            </ng-container>
            <ng-template #noPrediction><p class="muted">The linked prediction is no longer available.</p></ng-template>
          </section>

          <section class="card information-card" aria-labelledby="lifecycle-title">
            <h2 id="lifecycle-title">Lifecycle history</h2>
            <dl>
              <div><dt>Acknowledged by</dt><dd>{{ current.acknowledged_by || 'Not acknowledged' }}</dd></div>
              <div><dt>Acknowledged at</dt><dd>{{ current.acknowledged_at ? (current.acknowledged_at | date:'medium') : '—' }}</dd></div>
              <div><dt>Resolved by</dt><dd>{{ current.resolved_by || (current.resolution_source === 'AUTO' ? 'Automatically' : 'Not resolved') }}</dd></div>
              <div><dt>Resolved at</dt><dd>{{ current.resolved_at ? (current.resolved_at | date:'medium') : '—' }}</dd></div>
              <div><dt>Resolution source</dt><dd>{{ current.resolution_source || '—' }}</dd></div>
            </dl>
          </section>
        </div>
      </ng-container>
    </section>
  `,
  styles: [`
    .alert-detail-page { display: flex; flex-direction: column; gap: 1rem; color: var(--text-main); }
    .back-link { color: var(--text-muted); text-decoration: none; width: fit-content; }
    .back-link:hover { color: var(--primary); }
    .detail-heading { display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 1.25rem; }
    .eyebrow { margin: 0 0 .25rem; color: var(--text-muted); font-size: .68rem; font-weight: 700; letter-spacing: .08em; }
    h1 { margin: 0 0 .65rem; font-size: 1.5rem; }
    h2 { margin: 0 0 1rem; font-size: 1rem; }
    .badges, .actions { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }
    .status-badge, .severity { display: inline-flex; border-radius: 999px; padding: .25rem .6rem; font-size: .72rem; font-weight: 700; }
    .status-open { color: #991b1b; background: #fee2e2; }
    .status-acknowledged { color: #854d0e; background: #fef3c7; }
    .status-resolved { color: #166534; background: #dcfce7; }
    .severity-high { color: #9a3412; background: #ffedd5; }
    .severity-critical { color: #991b1b; background: #fee2e2; }
    .detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
    .information-card { padding: 1.2rem; }
    dl { display: grid; gap: .75rem; margin: 0; }
    dl > div { display: grid; grid-template-columns: minmax(110px, .7fr) 1.3fr; gap: .8rem; }
    dt { color: var(--text-muted); font-size: .82rem; }
    dd { margin: 0; font-size: .86rem; overflow-wrap: anywhere; }
    .resource-name { font-size: 1.05rem; font-weight: 700; }
    .resource-identifier, .muted, .note { color: var(--text-muted); }
    .note { margin: 1rem 0 0; font-size: .78rem; }
    .state-card { padding: 1.25rem; border: 1px solid var(--border-color); border-radius: var(--radius-md); background: white; }
    .error-state { color: #991b1b; }
    @media (max-width: 720px) { .detail-heading { align-items: flex-start; flex-direction: column; } .detail-grid { grid-template-columns: 1fr; } }
  `],
})
export class AlertDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private alertService = inject(AlertService);
  private authService = inject(AuthService);
  private changeDetector = inject(ChangeDetectorRef);
  private destroyRef = inject(DestroyRef);

  alert: Alert | null = null;
  alertId = '';
  loading = true;
  loadError = '';
  actionError = '';
  actionInProgress: 'acknowledge' | 'resolve' | null = null;
  readonly canManage = this.authService.isITProOrSysAdmin;
  private loadSequence = 0;
  private actionSequence = 0;

  ngOnInit(): void {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      this.alertId = params.get('id') ?? '';
      this.actionSequence++;
      this.actionInProgress = null;
      this.loadAlert();
    });
  }

  loadAlert(): void {
    const sequence = ++this.loadSequence;
    this.loading = true;
    this.loadError = '';
    this.actionError = '';
    this.alert = null;
    this.alertService.getAlert(this.alertId).subscribe({
      next: (alert) => {
        if (sequence !== this.loadSequence) return;
        this.alert = alert;
        this.loading = false;
        this.changeDetector.markForCheck();
      },
      error: () => {
        if (sequence !== this.loadSequence) return;
        this.loading = false;
        this.loadError = 'Alert details could not be loaded. It may no longer be available.';
        this.changeDetector.markForCheck();
      },
    });
  }

  acknowledge(): void { this.performAction('acknowledge'); }
  resolve(): void {
    if (!this.alert || this.actionInProgress || !this.canManage()) return;
    if (!window.confirm(`Resolve the active alert for ${this.alert.resource.identifier}?`)) return;
    this.performAction('resolve');
  }

  private performAction(action: 'acknowledge' | 'resolve'): void {
    if (!this.alert || this.actionInProgress || !this.canManage()) return;
    const alertId = this.alert.id;
    const actionSequence = ++this.actionSequence;
    this.actionInProgress = action;
    this.actionError = '';
    const request = action === 'acknowledge'
      ? this.alertService.acknowledge(alertId)
      : this.alertService.resolve(alertId);
    request.subscribe({
      next: (updated) => {
        if (actionSequence !== this.actionSequence || alertId !== this.alertId) return;
        this.alert = updated;
        this.actionInProgress = null;
        this.alertService.refreshUnreadCount().subscribe();
        this.changeDetector.markForCheck();
      },
      error: (error) => {
        if (actionSequence !== this.actionSequence || alertId !== this.alertId) return;
        if (error?.status === 409) {
          this.actionError = 'This alert changed state before the action completed. Its latest state has been reloaded.';
        } else if (error?.status === 403) {
          this.actionError = 'Your role cannot change this alert.';
        } else {
          this.actionError = 'The action response could not be confirmed. The latest alert state is being checked.';
        }
        this.changeDetector.markForCheck();
        this.recoverAlertState(alertId, actionSequence);
      },
    });
  }

  private recoverAlertState(alertId: string, actionSequence: number): void {
    const sequence = ++this.loadSequence;
    this.loading = true;
    this.loadError = '';
    this.alert = null;
    this.alertService.getAlert(this.alertId).subscribe({
      next: (alert) => {
        if (sequence !== this.loadSequence || actionSequence !== this.actionSequence || alertId !== this.alertId) return;
        this.alert = alert;
        this.loading = false;
        this.alertService.refreshUnreadCount().subscribe();
        this.actionInProgress = null;
        this.changeDetector.markForCheck();
      },
      error: () => {
        if (sequence !== this.loadSequence || actionSequence !== this.actionSequence || alertId !== this.alertId) return;
        this.loading = false;
        this.loadError = 'The alert state could not be refreshed. Retry to confirm its current state.';
        this.actionInProgress = null;
        this.changeDetector.markForCheck();
      },
    });
  }
}
