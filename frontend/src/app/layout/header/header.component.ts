import { ChangeDetectorRef, Component, DestroyRef, EventEmitter, OnInit, Output, effect, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { interval } from 'rxjs';
import { DashboardService } from '../../core/services/dashboard.service';
import { AlertService } from '../../core/services/alert.service';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <header class="app-header">
      <div class="header-left">
        <button class="toggle-sidebar-btn" (click)="toggleSidebar.emit()" title="Toggle sidebar">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
        <div class="system-status-indicator" [class.is-online]="aiStatus === 'online'" [class.is-offline]="aiStatus === 'offline'" [class.is-checking]="aiStatus === 'checking'" role="status" aria-live="polite">
          <span class="status-dot"></span>
          <span class="status-label">{{ aiStatusLabel }}</span>
          <span class="status-constraints" title="Models use the current 22 SMART features and existing prediction windows">
            {{ aiModelVersion || (aiStatus === 'offline' ? 'Health check unavailable' : 'GRU & LSTM-AE') }}
          </span>
        </div>
      </div>
      <div class="header-actions">
        <ng-container *ngIf="{ count: (unreadCount$ | async) } as alertCount">
        <a *ngIf="currentUser()" class="notification-link" routerLink="/alerts"
           [attr.aria-label]="alertLabel(alertCount.count)"
           [attr.title]="alertLabel(alertCount.count)">
          <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/>
            <path d="M10 21h4"/>
          </svg>
          <span class="screen-reader-only" aria-live="polite">
            {{ alertCount.count === null ? 'Open alert count unavailable' : alertCount.count === 0 ? 'No open alerts' : alertCount.count + ' open alerts' }}
          </span>
          <span *ngIf="alertCount.count !== null && alertCount.count > 0" class="notification-count" aria-hidden="true">
            {{ alertCount.count > 99 ? '99+' : alertCount.count }}
          </span>
        </a>
        </ng-container>
      </div>

    </header>
  `,
  styles: [`
    .app-header {
      height: 60px;
      background: #ffffff;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 1.5rem;
      position: sticky;
      top: 0;
      z-index: 90;
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 1.25rem;

      .toggle-sidebar-btn {
        color: var(--text-muted);
        padding: 0.4rem;
        border-radius: var(--radius-sm);
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.15s ease;

        &:hover {
          color: var(--text-main);
          background: #f1f5f9;
        }
      }

      .system-status-indicator {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        background: #f8fafc;
        border: 1px solid var(--border-color);
        padding: 0.3rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.775rem;

        .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #94a3b8;
        }

        .status-label {
          font-weight: 600;
          color: #0f172a;
        }

        .status-constraints {
          color: var(--text-muted);
          border-left: 1px solid var(--border-color);
          padding-left: 0.5rem;
          font-size: 0.725rem;
        }

        &.is-online .status-dot {
          background: #10b981;
          box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2);
        }

        &.is-offline .status-dot {
          background: #ef4444;
          box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15);
        }

        &.is-checking .status-dot {
          background: #f59e0b;
          box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15);
        }

        &.is-offline .status-label { color: #b91c1c; }
      }
    }

    .header-actions {
      display: flex;
      align-items: center;
      margin-left: auto;
      padding-left: 1rem;
    }

    .notification-link {
      position: relative;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 38px;
      height: 38px;
      border-radius: 9999px;
      color: var(--text-muted);
      text-decoration: none;
    }

    .notification-link:hover {
      color: var(--primary);
      background: #eff6ff;
    }

    .notification-link:focus-visible {
      color: var(--primary);
      background: #eff6ff;
      outline: 2px solid var(--primary);
      outline-offset: 2px;
    }

    .notification-count {
      position: absolute;
      top: 0;
      right: -2px;
      min-width: 17px;
      height: 17px;
      padding: 0 4px;
      border-radius: 9999px;
      background: #dc2626;
      color: #fff;
      font-size: 0.65rem;
      font-weight: 700;
      line-height: 17px;
      text-align: center;
    }

    .screen-reader-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }

    @keyframes pulse {
      0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
      70% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
      100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    @media (max-width: 700px) {
      .app-header { padding: 0 0.75rem; }
      .header-left { gap: 0.5rem; }
      .system-status-indicator {
        gap: 0.35rem;
        padding: 0.3rem 0.5rem;
        .status-constraints { display: none; }
        .status-label { font-size: 0.68rem; }
      }
    }
  `],
})
export class HeaderComponent implements OnInit {
  @Output() toggleSidebar = new EventEmitter<void>();

  private dashboardService = inject(DashboardService);
  private alertService = inject(AlertService);
  private authService = inject(AuthService);
  private changeDetector = inject(ChangeDetectorRef);
  private destroyRef = inject(DestroyRef);
  readonly currentUser = this.authService.currentUser;
  private activeUserId: string | null | undefined;
  private readonly unreadCountSessionEffect = effect(() => {
    const userId = this.currentUser()?.id ?? null;
    if (userId === this.activeUserId) return;
    this.activeUserId = userId;
    this.alertService.clearUnreadCount();
    if (userId) {
      this.alertService.refreshUnreadCount()
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe();
    }
  });

  aiStatus: 'checking' | 'online' | 'offline' = 'checking';
  aiModelVersion: string | null = null;
  readonly unreadCount$ = this.alertService.unreadCount$;

  get aiStatusLabel(): string {
    if (this.aiStatus === 'online') return 'Predictive Engine Online';
    if (this.aiStatus === 'offline') return 'Predictive Engine Offline';
    return 'Checking AI service';
  }

  ngOnInit(): void {
    this.refreshAiStatus();
    interval(30_000)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.refreshAiStatus());
  }

  alertLabel(count: number | null): string {
    if (count === null) return 'Alerts, open-alert count unavailable';
    if (count === 0) return 'Alerts, no open alerts';
    return `Alerts, ${count} open alert${count === 1 ? '' : 's'}`;
  }

  private refreshAiStatus(): void {
    this.dashboardService.getInferenceHealth().subscribe({
      next: (health) => {
        this.aiStatus = health.status;
        this.aiModelVersion = health.model_version;
        this.changeDetector.markForCheck();
      },
      error: () => {
        this.aiStatus = 'offline';
        this.aiModelVersion = null;
        this.changeDetector.markForCheck();
      },
    });
  }
}
