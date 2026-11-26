import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, DestroyRef, Input, OnChanges, OnInit, SimpleChanges, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Subject, catchError, switchMap } from 'rxjs';
import {
  DriveTimelineEvent,
  DriveTimelineEventType,
  DriveTimelinePage,
  DriveTimelineQuery,
} from '../../../core/models/drive.models';
import { DriveService } from '../../../core/services/drive.service';

@Component({
  selector: 'app-drive-timeline',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <section class="card timeline-card" aria-labelledby="drive-timeline-title">
      <div class="timeline-heading">
        <div>
          <h2 id="drive-timeline-title">Operational timeline</h2>
          <p class="text-muted">Telemetry, predictions, alerts and recorded drive changes.</p>
        </div>
        <button type="button" class="btn btn-secondary btn-sm" (click)="clearFilters()" [disabled]="!hasFilters || timelineLoading">
          Clear filters
        </button>
      </div>

      <div class="timeline-filters" aria-label="Timeline filters">
        <label>
          <span>Event type</span>
          <select [(ngModel)]="selectedType" (ngModelChange)="filtersChanged()" aria-label="Filter timeline by event type">
            <option value="">All event types</option>
            <option value="TELEMETRY_READING">SMART telemetry</option>
            <option value="PREDICTION">Predictions</option>
            <option value="ALERT_OPENED">Alert opened</option>
            <option value="ALERT_ACKNOWLEDGED">Alert acknowledged</option>
            <option value="ALERT_RESOLVED">Alert resolved</option>
            <option value="RESOURCE_AUDIT">Resource changes</option>
          </select>
        </label>
        <label>
          <span>From</span>
          <input type="date" [(ngModel)]="fromDate" (ngModelChange)="filtersChanged()" aria-label="Timeline from date">
        </label>
        <label>
          <span>To</span>
          <input type="date" [(ngModel)]="toDate" (ngModelChange)="filtersChanged()" aria-label="Timeline to date">
        </label>
      </div>

      <p *ngIf="timelineLoading" class="timeline-state" role="status">Loading timeline…</p>
      <p *ngIf="dateRangeError" class="timeline-state error-state" role="alert">{{ dateRangeError }}</p>
      <div *ngIf="timelineError" class="timeline-state error-state" role="alert">
        <span>The drive timeline could not be loaded.</span>
        <button type="button" class="btn btn-secondary btn-sm" (click)="retry()">Try again</button>
      </div>
      <p *ngIf="!timelineLoading && !timelineError && !dateRangeError && events.length === 0 && !hasFilters" class="timeline-state empty-state">
        No timeline events are available for this drive.
      </p>
      <p *ngIf="!timelineLoading && !timelineError && !dateRangeError && events.length === 0 && hasFilters" class="timeline-state empty-state">
        No events match the selected filters.
      </p>

      <ol *ngIf="!timelineLoading && !timelineError && !dateRangeError && events.length" class="timeline-list" aria-label="Drive operational events">
        <li *ngFor="let event of events" class="timeline-event" [ngClass]="eventClass(event.event_type)">
          <span class="event-marker" aria-hidden="true"></span>
          <article class="event-content">
            <div class="event-title-row">
              <h3>{{ eventTitle(event) }}</h3>
              <span class="event-type-badge">{{ eventLabel(event.event_type) }}</span>
            </div>
            <time class="event-time" [attr.datetime]="event.occurred_at">{{ event.occurred_at | date:'medium' }}</time>

            <ng-container [ngSwitch]="event.event_type">
              <div *ngSwitchCase="'TELEMETRY_READING'" class="event-metadata">
                <span>Source: {{ event.data.source || 'Not specified' }}</span>
              </div>

              <div *ngSwitchCase="'PREDICTION'" class="event-metadata">
                <ng-container *ngIf="event.data.prediction_type === 'FAILURE_PREDICTION'; else anomalyPrediction">
                  <span>Failure risk: {{ event.data.risk_level || 'Not available' }}</span>
                  <span *ngIf="event.data.horizon_days !== null && event.data.horizon_days !== undefined">Horizon: {{ event.data.horizon_days }} days</span>
                </ng-container>
                <ng-template #anomalyPrediction>
                  <span>Anomaly: {{ event.data.is_anomalous === true ? 'Detected' : event.data.is_anomalous === false ? 'Not detected' : 'Not available' }}</span>
                </ng-template>
                <span *ngIf="event.data.score !== undefined">Score: {{ event.data.score | number:'1.3-4' }}</span>
                <span *ngIf="event.data.model as model">Model: {{ model.name }} {{ model.version }} ({{ model.architecture }})</span>
                <span *ngIf="event.data.window_start && event.data.window_end">
                  Window:
                  <time [attr.datetime]="event.data.window_start">{{ event.data.window_start | date:'medium' }}</time>
                  – <time [attr.datetime]="event.data.window_end">{{ event.data.window_end | date:'medium' }}</time>
                </span>
              </div>

              <div *ngSwitchCase="'ALERT_OPENED'" class="event-metadata">
                <span>{{ event.data.alert_type === 'FAILURE_RISK' ? 'Failure risk' : 'Anomaly' }} · {{ event.data.severity }}</span>
              </div>
              <div *ngSwitchCase="'ALERT_ACKNOWLEDGED'" class="event-metadata">
                <span>{{ event.data.alert_type === 'FAILURE_RISK' ? 'Failure risk' : 'Anomaly' }} · {{ event.data.severity }}</span>
              </div>
              <div *ngSwitchCase="'ALERT_RESOLVED'" class="event-metadata">
                <span>{{ event.data.alert_type === 'FAILURE_RISK' ? 'Failure risk' : 'Anomaly' }} · {{ event.data.severity }}</span>
                <span *ngIf="event.data.resolution_source">Resolution: {{ event.data.resolution_source === 'AUTO' ? 'Automatic' : 'Manual' }}</span>
              </div>

              <div *ngSwitchCase="'RESOURCE_AUDIT'" class="event-metadata">
                <span>{{ event.data.description }}</span>
                <span *ngIf="event.data.action">Action: {{ event.data.action }}</span>
              </div>
            </ng-container>

            <p *ngIf="event.actor" class="event-actor">Actor: {{ event.actor }}</p>
            <a *ngIf="isAlertEvent(event) && event.data.alert_id" [routerLink]="['/alerts', event.data.alert_id]" class="event-link">
              View alert
            </a>
          </article>
        </li>
      </ol>

      <nav *ngIf="!timelineError && !dateRangeError && timelinePage && timelinePage.count > 0" class="timeline-pagination" aria-label="Timeline pagination">
        <button type="button" class="btn btn-secondary btn-sm" (click)="goToPage(page - 1)" [disabled]="!timelinePage.previous || timelineLoading">Previous</button>
        <span aria-live="polite">Page {{ page }} of {{ totalPages }} · {{ timelinePage.count }} events</span>
        <button type="button" class="btn btn-secondary btn-sm" (click)="goToPage(page + 1)" [disabled]="!timelinePage.next || timelineLoading">Next</button>
      </nav>
    </section>
  `,
  styles: [`
    .timeline-card { padding: 1.25rem; }
    .timeline-heading, .event-title-row, .timeline-pagination { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
    .timeline-heading h2 { margin: 0; font-size: 1.1rem; }
    .timeline-heading p { margin: .3rem 0 0; font-size: .85rem; }
    .timeline-filters { display: flex; flex-wrap: wrap; gap: .75rem; margin: 1rem 0; }
    .timeline-filters label { display: grid; gap: .25rem; min-width: 9rem; color: var(--text-muted); font-size: .78rem; }
    .timeline-filters select, .timeline-filters input { min-height: 2.25rem; padding: .35rem .5rem; border: 1px solid var(--border-color); border-radius: .4rem; color: var(--text-main); background: var(--surface, #fff); }
    .timeline-state { padding: 1rem 0; }
    .error-state { display: flex; align-items: center; gap: .75rem; color: var(--danger, #b91c1c); }
    .timeline-list { list-style: none; margin: 1.25rem 0; padding: 0 0 0 .5rem; border-left: 2px solid var(--border-color); }
    .timeline-event { position: relative; padding: 0 0 1.25rem 1.1rem; }
    .event-marker { position: absolute; left: -.9rem; top: .2rem; width: .75rem; height: .75rem; border: 2px solid var(--primary, #2563eb); border-radius: 50%; background: var(--surface, #fff); }
    .event-prediction .event-marker { border-color: #7c3aed; }
    .event-alert .event-marker { border-color: #dc2626; }
    .event-audit .event-marker { border-color: #64748b; }
    .event-content h3 { margin: 0; font-size: .95rem; }
    .event-type-badge { padding: .15rem .45rem; border-radius: 999px; background: var(--surface-muted, #f1f5f9); color: var(--text-muted); font-size: .7rem; }
    .event-time, .event-actor { display: block; margin-top: .25rem; color: var(--text-muted); font-size: .78rem; }
    .event-metadata { display: flex; flex-wrap: wrap; gap: .4rem 1rem; margin-top: .45rem; font-size: .83rem; }
    .event-link { display: inline-block; margin-top: .4rem; font-size: .82rem; }
    .timeline-pagination { justify-content: flex-end; padding-top: .75rem; border-top: 1px solid var(--border-color); }
    .timeline-pagination span { color: var(--text-muted); font-size: .8rem; }
    @media (max-width: 600px) {
      .timeline-heading { align-items: flex-start; }
      .timeline-filters { display: grid; grid-template-columns: 1fr 1fr; }
      .timeline-filters label:first-child { grid-column: 1 / -1; }
      .timeline-pagination { flex-wrap: wrap; }
    }
  `],
})
export class DriveTimelineComponent implements OnInit, OnChanges {
  @Input({ required: true }) driveId = '';
  @Input() refreshToken = 0;

  private readonly driveService = inject(DriveService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly requests = new Subject<DriveTimelineQuery | null>();

  events: DriveTimelineEvent[] = [];
  timelinePage: DriveTimelinePage | null = null;
  timelineLoading = true;
  timelineError = false;
  dateRangeError = '';
  page = 1;
  readonly pageSize = 20;
  selectedType: DriveTimelineEventType | '' = '';
  fromDate = '';
  toDate = '';
  private initialized = false;

  ngOnInit(): void {
    this.requests.pipe(
      switchMap((query) => {
        if (query === null) {
          this.timelineLoading = false;
          this.timelineError = false;
          this.timelinePage = null;
          this.events = [];
          this.changeDetector.markForCheck();
          return EMPTY;
        }
        this.timelineLoading = true;
        this.timelineError = false;
        this.events = [];
        this.changeDetector.markForCheck();
        return this.driveService.getTimeline(this.driveId, query).pipe(
          catchError(() => {
            this.timelineLoading = false;
            this.timelineError = true;
            this.timelinePage = null;
            this.changeDetector.markForCheck();
            return EMPTY;
          }),
        );
      }),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((page) => {
      this.timelinePage = page;
      this.events = page.results;
      this.timelineLoading = false;
      this.changeDetector.markForCheck();
    });
    this.initialized = true;
    this.loadPage();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (!this.initialized) return;
    if (changes['driveId'] && !changes['driveId'].firstChange) {
      this.page = 1;
      this.loadPage();
      return;
    }
    if (changes['refreshToken']) this.loadPage();
  }

  get hasFilters(): boolean {
    return Boolean(this.selectedType || this.fromDate || this.toDate);
  }

  get totalPages(): number {
    return Math.max(1, Math.ceil((this.timelinePage?.count ?? 0) / this.pageSize));
  }

  filtersChanged(): void {
    this.page = 1;
    this.loadPage();
  }

  clearFilters(): void {
    this.selectedType = '';
    this.fromDate = '';
    this.toDate = '';
    this.page = 1;
    this.loadPage();
  }

  retry(): void {
    this.loadPage();
  }

  goToPage(page: number): void {
    if (page < 1 || page > this.totalPages || page === this.page) return;
    this.page = page;
    this.loadPage();
  }

  eventLabel(type: DriveTimelineEventType): string {
    return ({
      TELEMETRY_READING: 'SMART telemetry',
      PREDICTION: 'Prediction',
      ALERT_OPENED: 'Alert opened',
      ALERT_ACKNOWLEDGED: 'Alert acknowledged',
      ALERT_RESOLVED: 'Alert resolved',
      RESOURCE_AUDIT: 'Resource change',
    })[type];
  }

  eventTitle(event: DriveTimelineEvent): string {
    if (event.event_type === 'PREDICTION') {
      return event.data.prediction_type === 'FAILURE_PREDICTION' ? 'Failure-risk prediction' : 'Anomaly prediction';
    }
    if (event.event_type === 'ALERT_OPENED') return 'Alert opened';
    if (event.event_type === 'ALERT_ACKNOWLEDGED') return 'Alert acknowledged';
    if (event.event_type === 'ALERT_RESOLVED') return 'Alert resolved';
    if (event.event_type === 'RESOURCE_AUDIT') return event.data.description || 'Resource change';
    return 'SMART telemetry reading';
  }

  eventClass(type: DriveTimelineEventType): string {
    if (type === 'PREDICTION') return 'event-prediction';
    if (type.startsWith('ALERT_')) return 'event-alert';
    if (type === 'RESOURCE_AUDIT') return 'event-audit';
    return 'event-telemetry';
  }

  isAlertEvent(event: DriveTimelineEvent): boolean {
    return event.event_type === 'ALERT_OPENED'
      || event.event_type === 'ALERT_ACKNOWLEDGED'
      || event.event_type === 'ALERT_RESOLVED';
  }

  private loadPage(): void {
    if (this.fromDate && this.toDate && this.fromDate > this.toDate) {
      this.timelineLoading = false;
      this.timelineError = false;
      this.dateRangeError = 'From date must be on or before To date.';
      this.requests.next(null);
      return;
    }
    this.dateRangeError = '';
    this.timelinePage = null;
    this.requests.next({
      page: this.page,
      page_size: this.pageSize,
      type: this.selectedType,
      from: this.fromDate || undefined,
      to: this.toDate || undefined,
    });
  }
}
