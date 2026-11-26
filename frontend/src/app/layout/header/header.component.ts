import { ChangeDetectorRef, Component, DestroyRef, EventEmitter, OnInit, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { interval } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { DashboardService } from '../../core/services/dashboard.service';

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

      <div class="header-right">
        <a href="/api/docs/" target="_blank" rel="noopener noreferrer" class="header-action-btn" title="Open API Swagger">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
          </svg>
          <span>API Docs</span>
        </a>

        <div class="user-chip" routerLink="/profile">
          <div class="chip-avatar">{{ currentUser()?.username?.[0]?.toUpperCase() }}</div>
          <span class="chip-name">{{ currentUser()?.username }}</span>
          <span class="chip-role">{{ currentUser()?.role }}</span>
        </div>
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

    .header-right {
      display: flex;
      align-items: center;
      gap: 1rem;

      .header-action-btn {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        font-size: 0.8rem;
        font-weight: 500;
        color: var(--text-muted);
        padding: 0.35rem 0.65rem;
        border: 1px solid var(--border-color);
        border-radius: var(--radius-sm);
        text-decoration: none;
        transition: all 0.15s ease;

        &:hover {
          color: var(--primary);
          border-color: var(--primary);
          background: var(--primary-subtle);
        }
      }

      .user-chip {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.25rem 0.65rem 0.25rem 0.25rem;
        border-radius: 9999px;
        background: #f1f5f9;
        cursor: pointer;
        transition: all 0.15s ease;

        &:hover {
          background: #e2e8f0;
        }

        .chip-avatar {
          width: 26px;
          height: 26px;
          border-radius: 50%;
          background: var(--primary);
          color: #ffffff;
          font-weight: 600;
          font-size: 0.75rem;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .chip-name {
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--text-main);
        }

        .chip-role {
          font-size: 0.65rem;
          font-weight: 700;
          padding: 0.1rem 0.35rem;
          background: #ffffff;
          border-radius: 4px;
          color: var(--text-muted);
          border: 1px solid var(--border-color);
        }
      }
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
      .header-right { gap: 0.4rem; }
      .header-action-btn span, .chip-name { display: none; }
    }
  `],
})
export class HeaderComponent implements OnInit {
  @Output() toggleSidebar = new EventEmitter<void>();

  private authService = inject(AuthService);
  private dashboardService = inject(DashboardService);
  private changeDetector = inject(ChangeDetectorRef);
  private destroyRef = inject(DestroyRef);

  readonly currentUser = this.authService.currentUser;
  aiStatus: 'checking' | 'online' | 'offline' = 'checking';
  aiModelVersion: string | null = null;

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
