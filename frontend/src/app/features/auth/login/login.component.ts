import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="login-page">
      <div class="login-card">
        <div class="login-header">
          <div class="login-logo">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
            </svg>
          </div>
          <h1>DeepPredict</h1>
          <p class="subtitle">Enterprise SMART Predictive Maintenance Platform</p>
        </div>

        <form (ngSubmit)="onSubmit()" class="login-form">
          <div *ngIf="errorMessage" class="error-banner">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span>{{ errorMessage }}</span>
          </div>

          <div class="form-group">
            <label for="username">Username</label>
            <input
              id="username"
              type="text"
              name="username"
              [(ngModel)]="username"
              class="form-control"
              placeholder="e.g. admin"
              required
              autocomplete="username"
            />
          </div>

          <div class="form-group">
            <label for="password">Password</label>
            <div class="password-input-wrapper">
              <input
                id="password"
                [type]="showPassword ? 'text' : 'password'"
                name="password"
                [(ngModel)]="password"
                class="form-control"
                placeholder="••••••••"
                required
                autocomplete="current-password"
              />
              <button type="button" class="toggle-password" (click)="showPassword = !showPassword">
                {{ showPassword ? 'Hide' : 'Show' }}
              </button>
            </div>
          </div>

          <button type="submit" class="btn btn-primary submit-btn" [disabled]="loading || !username || !password">
            <span *ngIf="!loading">Sign In</span>
            <span *ngIf="loading">Signing In...</span>
          </button>
        </form>

        <div class="login-footer">
          <span>Protected by JWT Authentication with SimpleJWT & CORS</span>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .login-page {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: radial-gradient(circle at 50% 10%, #1e293b, #0f172a);
      padding: 1.5rem;
    }

    .login-card {
      width: 100%;
      max-width: 440px;
      background: #ffffff;
      border-radius: var(--radius-lg);
      padding: 2.25rem;
      box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.25), 0 8px 10px -6px rgb(0 0 0 / 0.25);
    }

    .login-header {
      text-align: center;
      margin-bottom: 2rem;

      .login-logo {
        width: 52px;
        height: 52px;
        margin: 0 auto 1rem;
        background: linear-gradient(135deg, #2563eb, #6366f1);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        box-shadow: 0 8px 16px rgba(37, 99, 235, 0.3);
      }

      h1 {
        font-size: 1.5rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.35rem;
      }

      .subtitle {
        font-size: 0.85rem;
        color: var(--text-muted);
      }
    }

    .error-banner {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.75rem 1rem;
      background: var(--danger-bg);
      border: 1px solid var(--danger-border);
      border-radius: var(--radius-sm);
      color: var(--danger-text);
      font-size: 0.825rem;
      margin-bottom: 1.25rem;
    }

    .password-input-wrapper {
      position: relative;
      display: flex;
      align-items: center;

      .form-control {
        width: 100%;
        padding-right: 4rem;
      }

      .toggle-password {
        position: absolute;
        right: 0.75rem;
        font-size: 0.75rem;
        color: var(--text-muted);
        font-weight: 600;
        &:hover {
          color: var(--text-main);
        }
      }
    }

    .submit-btn {
      width: 100%;
      padding: 0.75rem;
      font-size: 0.95rem;
      font-weight: 600;
      margin-top: 0.5rem;
    }


    .login-footer {
      margin-top: 1.5rem;
      text-align: center;
      font-size: 0.725rem;
      color: var(--text-muted);
    }
  `],
})
export class LoginComponent {
  private authService = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  username = '';
  password = '';
  showPassword = false;
  loading = false;
  errorMessage = '';

  onSubmit(): void {
    if (!this.username || !this.password) return;

    this.loading = true;
    this.errorMessage = '';

    this.authService.login({ username: this.username, password: this.password }).subscribe({
      next: () => {
        this.authService.fetchMe().subscribe({
          next: () => {
            const returnUrl = this.route.snapshot.queryParams['returnUrl'] || '/overview';
            this.router.navigateByUrl(returnUrl);
          },
          error: (err) => {
            this.loading = false;
            this.errorMessage = 'Authenticated but failed to retrieve user profile.';
          },
        });
      },
      error: (err) => {
        this.loading = false;
        if (err.status === 401) {
          this.errorMessage = 'Invalid username or password.';
        } else if (err.status === 429) {
          this.errorMessage = 'Too many failed login attempts. Please wait 1 minute.';
        } else {
          this.errorMessage = err.error?.detail || err.error?.non_field_errors?.[0] || 'Unable to connect to DeepPredict API.';
        }
      },
    });
  }
}
