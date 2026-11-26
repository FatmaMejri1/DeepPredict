import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="profile-page">
      <div class="page-header">
        <div>
          <h1 class="page-title">Account Settings & Security</h1>
          <p class="page-subtitle">Manage personal profile details and authentication credentials.</p>
        </div>
      </div>

      <div class="profile-grid">
        <!-- Account Info Card -->
        <div class="card info-card" *ngIf="currentUser()">
          <div class="card-header">
            <h3>Profile Information</h3>
            <span class="badge" [class.badge-anomaly]="currentUser()?.role === 'SYSADMIN'" [class.badge-warning]="currentUser()?.role === 'IT_PRO'" [class.badge-healthy]="currentUser()?.role === 'OPERATOR'">
              {{ currentUser()?.role }}
            </span>
          </div>

          <div class="user-profile-header">
            <div class="profile-avatar">
              {{ currentUser()?.username?.substring(0, 2)?.toUpperCase() }}
            </div>
            <div>
              <h2 class="profile-username">{{ currentUser()?.username }}</h2>
              <span class="profile-email">{{ currentUser()?.email }}</span>
            </div>
          </div>

          <div class="details-list">
            <div class="detail-item">
              <span class="detail-label">Assigned Permissions Role</span>
              <span class="detail-value">
                <strong>{{ currentUser()?.role }}</strong> —
                <span *ngIf="currentUser()?.role === 'SYSADMIN'">Full system administration, user provisioning, and monitoring.</span>
                <span *ngIf="currentUser()?.role === 'IT_PRO'">Operational access: telemetry uploads and AI predictions.</span>
                <span *ngIf="currentUser()?.role === 'OPERATOR'">Read-only access to drive health and model transparency reports.</span>
              </span>
            </div>

            <div class="detail-item">
              <span class="detail-label">Authentication Method</span>
              <span class="detail-value font-mono">SimpleJWT (Bearer Token with Automated Refresh)</span>
            </div>

            <div class="detail-item">
              <span class="detail-label">Account Registered</span>
              <span class="detail-value">{{ currentUser()?.date_joined | date:'medium' }}</span>
            </div>

            <div class="detail-item">
              <span class="detail-label">Last Active Session</span>
              <span class="detail-value">{{ currentUser()?.last_login ? (currentUser()?.last_login | date:'medium') : 'Current Session' }}</span>
            </div>
          </div>

          <div class="logout-section">
            <button class="btn btn-secondary btn-sm" (click)="onLogout()">
              Sign Out of Account
            </button>
          </div>
        </div>

        <!-- Change Password Card -->
        <div class="card password-card">
          <div class="card-header">
            <h3>Change Password</h3>
          </div>

          <form (ngSubmit)="onChangePassword()">
            <div *ngIf="successMsg" class="alert-success">
              {{ successMsg }}
            </div>
            <div *ngIf="errorMsg" class="alert-error">
              {{ errorMsg }}
            </div>

            <div class="form-group">
              <label for="old-pw">Current Password *</label>
              <input id="old-pw" type="password" [(ngModel)]="oldPassword" name="oldPassword" class="form-control" required />
            </div>

            <div class="form-group">
              <label for="new-pw">New Password *</label>
              <input id="new-pw" type="password" [(ngModel)]="newPassword" name="newPassword" class="form-control" required minlength="8" />
              <span class="form-hint">Minimum 8 characters. Avoid common or simple phrases.</span>
            </div>

            <div class="form-group">
              <label for="confirm-pw">Confirm New Password *</label>
              <input id="confirm-pw" type="password" [(ngModel)]="confirmPassword" name="confirmPassword" class="form-control" required />
            </div>

            <button type="submit" class="btn btn-primary" [disabled]="loading || !oldPassword || !newPassword || !confirmPassword">
              <span>{{ loading ? 'Updating Password...' : 'Update Password' }}</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .profile-page {
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

    .profile-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 1.5rem;
    }

    .info-card {
      .user-profile-header {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1.5rem;
        padding-bottom: 1.25rem;
        border-bottom: 1px solid var(--border-subtle);

        .profile-avatar {
          width: 54px;
          height: 54px;
          border-radius: 50%;
          background: #334155;
          color: #ffffff;
          font-weight: 700;
          font-size: 1.25rem;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .profile-username {
          font-size: 1.25rem;
          font-weight: 700;
          color: #0f172a;
        }

        .profile-email {
          font-size: 0.85rem;
          color: var(--text-muted);
        }
      }

      .details-list {
        display: flex;
        flex-direction: column;
        gap: 1rem;

        .detail-item {
          display: flex;
          flex-direction: column;
          gap: 0.2rem;

          .detail-label {
            font-size: 0.725rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
          }

          .detail-value {
            font-size: 0.875rem;
            color: var(--text-main);
          }
        }
      }

      .logout-section {
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid var(--border-subtle);
      }
    }

    .password-card {
      .alert-success {
        padding: 0.75rem 1rem;
        background: var(--success-bg);
        border: 1px solid var(--success-border);
        border-radius: var(--radius-sm);
        color: var(--success-text);
        font-size: 0.825rem;
        margin-bottom: 1.25rem;
      }

      .alert-error {
        padding: 0.75rem 1rem;
        background: var(--danger-bg);
        border: 1px solid var(--danger-border);
        border-radius: var(--radius-sm);
        color: var(--danger-text);
        font-size: 0.825rem;
        margin-bottom: 1.25rem;
      }
    }

    .font-mono {
      font-family: ui-monospace, SFMono-Regular, monospace;
    }
  `],
})
export class ProfileComponent {
  private authService = inject(AuthService);

  readonly currentUser = this.authService.currentUser;

  oldPassword = '';
  newPassword = '';
  confirmPassword = '';
  loading = false;
  successMsg = '';
  errorMsg = '';

  onChangePassword(): void {
    if (this.newPassword !== this.confirmPassword) {
      this.errorMsg = 'New passwords do not match.';
      return;
    }

    this.loading = true;
    this.successMsg = '';
    this.errorMsg = '';

    this.authService.changePassword({ old_password: this.oldPassword, new_password: this.newPassword }).subscribe({
      next: () => {
        this.loading = false;
        this.successMsg = 'Password successfully updated.';
        this.oldPassword = '';
        this.newPassword = '';
        this.confirmPassword = '';
      },
      error: (err) => {
        this.loading = false;
        this.errorMsg = err.error?.detail || err.error?.old_password?.[0] || err.error?.new_password?.[0] || 'Failed to update password.';
      },
    });
  }

  onLogout(): void {
    this.authService.logout();
  }
}
