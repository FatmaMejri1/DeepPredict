import { Component, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <aside class="sidebar" [class.collapsed]="collapsed">
      <div class="sidebar-header">
        <div class="brand">
          <div class="brand-logo">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
            </svg>
          </div>
          <div class="brand-text" *ngIf="!collapsed">
            <span class="brand-name">DeepPredict</span>
            <span class="brand-tag">Enterprise AI</span>
          </div>
        </div>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-section-title" *ngIf="!collapsed">FLEET MONITORING</div>
        <a routerLink="/overview" routerLinkActive="active" class="nav-item" title="Overview">
          <span class="nav-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/>
              <rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>
            </svg>
          </span>
          <span class="nav-label" *ngIf="!collapsed">Overview</span>
        </a>

        <a routerLink="/drives" routerLinkActive="active" class="nav-item" title="Drives Inventory">
          <span class="nav-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect width="20" height="8" x="2" y="3" rx="2"/><rect width="20" height="8" x="2" y="13" rx="2"/>
              <circle cx="6" cy="7" r="1" fill="currentColor"/><circle cx="6" cy="17" r="1" fill="currentColor"/>
            </svg>
          </span>
          <span class="nav-label" *ngIf="!collapsed">Drives Inventory</span>
        </a>

        <a routerLink="/high-risk-drives" routerLinkActive="active" class="nav-item" title="High-Risk Drives">
          <span class="nav-icon" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v4m0 3h.01"/>
            </svg>
          </span>
          <span class="nav-label" *ngIf="!collapsed">High-Risk Drives</span>
        </a>

        <a routerLink="/alerts" routerLinkActive="active" class="nav-item" title="Alerts">
          <span class="nav-icon" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/>
            </svg>
          </span>
          <span class="nav-label" *ngIf="!collapsed">Alerts</span>
        </a>

        <div class="nav-section-title" *ngIf="!collapsed">AI & TELEMETRY</div>
        <a *ngIf="isITProOrSysAdmin()" routerLink="/upload" routerLinkActive="active" class="nav-item" title="Upload Telemetry">
          <span class="nav-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>
            </svg>
          </span>
          <span class="nav-label" *ngIf="!collapsed">Upload Telemetry</span>
        </a>

        <a routerLink="/validation" routerLinkActive="active" class="nav-item" title="Data Validation">
          <span class="nav-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="m9 11 3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
            </svg>
          </span>
          <span class="nav-label" *ngIf="!collapsed">Data Validation</span>
        </a>

        <a *ngIf="isITProOrSysAdmin()" routerLink="/predictions" routerLinkActive="active" class="nav-item" title="Inference Engine">
          <span class="nav-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="m13 2-2 2.5V8l3 3-5 5H4v4.5L2 22"/><path d="m14 14 3-3V7l-2-2.5L17 2"/>
              <circle cx="18" cy="18" r="3"/>
            </svg>
          </span>
          <span class="nav-label" *ngIf="!collapsed">Inference & Scoring</span>
        </a>

        <a routerLink="/models" routerLinkActive="active" class="nav-item" title="ML Models">
          <span class="nav-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z"/>
              <path d="M12 6v6l4 2"/>
            </svg>
          </span>
          <span class="nav-label" *ngIf="!collapsed">Model Registry</span>
        </a>

        <div class="nav-section-title" *ngIf="!collapsed && isSysAdmin()">ADMINISTRATION</div>
        <a *ngIf="isSysAdmin()" routerLink="/users" routerLinkActive="active" class="nav-item" title="User Management">
          <span class="nav-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
              <path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
          </span>
          <span class="nav-label" *ngIf="!collapsed">Users & Roles</span>
        </a>

        <a *ngIf="isSysAdmin()" routerLink="/audit-logs" routerLinkActive="active" class="nav-item" title="Audit Logs">
          <span class="nav-icon" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 4h16v16H4z"/><path d="M8 8h8M8 12h8M8 16h5"/>
            </svg>
          </span>
          <span class="nav-label" *ngIf="!collapsed">Audit Logs</span>
        </a>

      </nav>

      <div class="sidebar-footer">
        <a routerLink="/profile" class="user-profile-badge" title="Profile Settings">
          <div class="user-avatar">{{ userInitials() }}</div>
          <div class="user-info" *ngIf="!collapsed">
            <div class="user-name">{{ currentUser()?.username }}</div>
            <div class="user-role badge" [class.badge-healthy]="isOperator()" [class.badge-warning]="currentUser()?.role === 'IT_PRO'" [class.badge-anomaly]="isSysAdmin()">
              {{ currentUser()?.role }}
            </div>
          </div>
        </a>
        <button class="logout-btn" (click)="onLogout()" title="Sign out" *ngIf="!collapsed">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>
          </svg>
        </button>
      </div>
    </aside>
  `,
  styles: [`
    .sidebar {
      width: 250px;
      min-width: 250px;
      height: 100vh;
      background: var(--bg-sidebar);
      color: #cbd5e1;
      display: flex;
      flex-direction: column;
      border-right: 1px solid rgba(255, 255, 255, 0.08);
      transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      z-index: 100;

      &.collapsed {
        width: 68px;
        min-width: 68px;
      }
    }

    .sidebar-header {
      padding: 1.25rem 1.25rem 1rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);

      .brand {
        display: flex;
        align-items: center;
        gap: 0.75rem;

        .brand-logo {
          width: 36px;
          height: 36px;
          border-radius: 8px;
          background: linear-gradient(135deg, #2563eb, #6366f1);
          color: #ffffff;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4px 10px rgba(37, 99, 235, 0.3);
        }

        .brand-text {
          display: flex;
          flex-direction: column;

          .brand-name {
            font-size: 1.1rem;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: -0.02em;
          }

          .brand-tag {
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #94a3b8;
          }
        }
      }
    }

    .sidebar-nav {
      flex: 1;
      overflow-y: auto;
      padding: 1rem 0.75rem;
      display: flex;
      flex-direction: column;
      gap: 0.25rem;

      .nav-section-title {
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: #64748b;
        margin: 0.85rem 0.5rem 0.35rem;
      }

      .nav-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.65rem 0.75rem;
        border-radius: var(--radius-sm);
        color: #94a3b8;
        font-size: 0.875rem;
        font-weight: 500;
        transition: all 0.15s ease;

        &:hover {
          color: #ffffff;
          background: rgba(255, 255, 255, 0.05);
        }

        &.active {
          color: #ffffff;
          background: var(--bg-sidebar-active);
          box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
        }

        .nav-icon {
          display: flex;
          align-items: center;
          justify-content: center;
        }
      }
    }

    .sidebar-footer {
      padding: 1rem;
      border-top: 1px solid rgba(255, 255, 255, 0.06);
      display: flex;
      align-items: center;
      justify-content: space-between;

      .user-profile-badge {
        display: flex;
        align-items: center;
        gap: 0.65rem;
        text-decoration: none;

        .user-avatar {
          width: 34px;
          height: 34px;
          border-radius: 50%;
          background: #334155;
          color: #ffffff;
          font-weight: 600;
          font-size: 0.8rem;
          display: flex;
          align-items: center;
          justify-content: center;
          border: 1px solid rgba(255, 255, 255, 0.15);
        }

        .user-info {
          display: flex;
          flex-direction: column;
          gap: 0.15rem;

          .user-name {
            font-size: 0.825rem;
            font-weight: 600;
            color: #ffffff;
          }
          .user-role {
            font-size: 0.65rem;
            padding: 0.15rem 0.4rem;
          }
        }
      }

      .logout-btn {
        color: #94a3b8;
        padding: 0.4rem;
        border-radius: var(--radius-sm);
        transition: all 0.15s ease;

        &:hover {
          color: #ef4444;
          background: rgba(239, 68, 68, 0.1);
        }
      }
    }
  `],
})
export class SidebarComponent {
  private authService = inject(AuthService);

  collapsed = false;

  readonly currentUser = this.authService.currentUser;
  readonly isSysAdmin = this.authService.isSysAdmin;
  readonly isOperator = this.authService.isOperator;
  readonly isITProOrSysAdmin = this.authService.isITProOrSysAdmin;

  readonly userInitials = computed(() => {
    const username = this.currentUser()?.username || 'U';
    return username.substring(0, 2).toUpperCase();
  });

  onLogout(): void {
    this.authService.logout();
  }
}
