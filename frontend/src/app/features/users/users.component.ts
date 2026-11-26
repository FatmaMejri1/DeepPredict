import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { UserService } from '../../core/services/user.service';
import { UserListItem, CreateUserPayload } from '../../core/models/user.models';
import { Role } from '../../core/models/auth.models';

@Component({
  selector: 'app-users',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="users-page">
      <div class="page-header">
        <div>
          <h1 class="page-title">User Management</h1>
          <p class="page-subtitle">Manage system administrators, IT professionals, and monitoring operators.</p>
        </div>
        <div>
          <button class="btn btn-primary" (click)="openCreateModal()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            Add New User
          </button>
        </div>
      </div>

      <!-- Filters Toolbar -->
      <div class="card toolbar-card">
        <div class="search-box">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            type="text"
            [(ngModel)]="searchQuery"
            placeholder="Search by username or email..."
            class="search-input"
          />
        </div>

        <div class="filters-group">
          <select [(ngModel)]="roleFilter" class="form-select filter-select">
            <option value="">All Roles</option>
            <option value="SYSADMIN">System Administrator</option>
            <option value="IT_PRO">IT Professional</option>
            <option value="OPERATOR">Operator</option>
          </select>
        </div>
      </div>

      <!-- Users Table -->
      <div class="card table-card">
        <div class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Email Address</th>
                <th>System Role</th>
                <th>Account Status</th>
                <th>Date Joined</th>
                <th>Last Login</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let user of filteredUsers()">
                <td>
                  <div class="user-cell">
                    <div class="user-avatar-sm">{{ user.username.substring(0, 2).toUpperCase() }}</div>
                    <span class="user-username">{{ user.username }}</span>
                  </div>
                </td>
                <td>{{ user.email || '—' }}</td>
                <td>
                  <span class="badge" [class.badge-anomaly]="user.role === 'SYSADMIN'" [class.badge-warning]="user.role === 'IT_PRO'" [class.badge-healthy]="user.role === 'OPERATOR'">
                    {{ user.role }}
                  </span>
                </td>
                <td>
                  <span class="badge" [class.badge-passed]="user.is_active" [class.badge-error]="!user.is_active">
                    {{ user.is_active ? 'ACTIVE' : 'INACTIVE' }}
                  </span>
                </td>
                <td class="text-muted">{{ user.date_joined | date:'mediumDate' }}</td>
                <td class="text-muted">{{ user.last_login ? (user.last_login | date:'mediumDate') : 'Never' }}</td>
                <td>
                  <div class="actions-group">
                    <button class="btn btn-secondary btn-sm" (click)="openEditModal(user)" title="Edit user role">
                      Edit
                    </button>
                    <button class="btn btn-secondary btn-sm" (click)="openPasswordModal(user)" title="Reset password">
                      Reset Key
                    </button>
                    <button
                      class="btn btn-sm"
                      [class.btn-danger]="user.is_active"
                      [class.btn-primary]="!user.is_active"
                      (click)="toggleActive(user)"
                    >
                      {{ user.is_active ? 'Deactivate' : 'Activate' }}
                    </button>
                  </div>
                </td>
              </tr>
              <tr *ngIf="filteredUsers().length === 0">
                <td colspan="7" class="text-center py-4 text-muted">
                  No users found matching current filters.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Create User Modal -->
      <div class="modal-overlay" *ngIf="showCreateModal" (click)="closeModals()">
        <div class="modal-content" (click)="$event.stopPropagation()">
          <div class="card-header">
            <h3>Add New User</h3>
            <button class="btn btn-secondary btn-sm" (click)="closeModals()">✕</button>
          </div>

          <form (ngSubmit)="onCreateUser()">
            <div class="form-group">
              <label for="new-username">Username *</label>
              <input id="new-username" type="text" [(ngModel)]="newUsername" name="newUsername" class="form-control" required />
            </div>

            <div class="form-group">
              <label for="new-email">Email Address *</label>
              <input id="new-email" type="email" [(ngModel)]="newEmail" name="newEmail" class="form-control" required />
            </div>

            <div class="form-group">
              <label for="new-password">Initial Password *</label>
              <input id="new-password" type="password" [(ngModel)]="newPassword" name="newPassword" class="form-control" required />
            </div>

            <div class="form-group">
              <label for="new-role">Role *</label>
              <select id="new-role" [(ngModel)]="newRole" name="newRole" class="form-select">
                <option value="OPERATOR">Operator (Read-only access)</option>
                <option value="IT_PRO">IT Professional (Predictions & Uploads)</option>
                <option value="SYSADMIN">System Administrator (Full access)</option>
              </select>
            </div>

            <div *ngIf="modalError" class="modal-error">
              {{ modalError }}
            </div>

            <div class="modal-actions">
              <button type="button" class="btn btn-secondary" (click)="closeModals()">Cancel</button>
              <button type="submit" class="btn btn-primary" [disabled]="!newUsername || !newEmail || !newPassword">
                Create User
              </button>
            </div>
          </form>
        </div>
      </div>

      <!-- Edit User Modal -->
      <div class="modal-overlay" *ngIf="showEditModal && editingUser" (click)="closeModals()">
        <div class="modal-content" (click)="$event.stopPropagation()">
          <div class="card-header">
            <h3>Edit User: {{ editingUser.username }}</h3>
            <button class="btn btn-secondary btn-sm" (click)="closeModals()">✕</button>
          </div>

          <form (ngSubmit)="onUpdateUser()">
            <div class="form-group">
              <label for="edit-email">Email Address</label>
              <input id="edit-email" type="email" [(ngModel)]="editEmail" name="editEmail" class="form-control" />
            </div>

            <div class="form-group">
              <label for="edit-role">Role</label>
              <select id="edit-role" [(ngModel)]="editRole" name="editRole" class="form-select">
                <option value="OPERATOR">Operator</option>
                <option value="IT_PRO">IT Professional</option>
                <option value="SYSADMIN">System Administrator</option>
              </select>
            </div>

            <div *ngIf="modalError" class="modal-error">
              {{ modalError }}
            </div>

            <div class="modal-actions">
              <button type="button" class="btn btn-secondary" (click)="closeModals()">Cancel</button>
              <button type="submit" class="btn btn-primary">Save Changes</button>
            </div>
          </form>
        </div>
      </div>

      <!-- Reset Password Modal -->
      <div class="modal-overlay" *ngIf="showPasswordModal && editingUser" (click)="closeModals()">
        <div class="modal-content" (click)="$event.stopPropagation()">
          <div class="card-header">
            <h3>Reset Password: {{ editingUser.username }}</h3>
            <button class="btn btn-secondary btn-sm" (click)="closeModals()">✕</button>
          </div>

          <form (ngSubmit)="onResetPassword()">
            <div class="form-group">
              <label for="admin-reset-pw">New Administrator-Set Password *</label>
              <input id="admin-reset-pw" type="password" [(ngModel)]="resetPasswordValue" name="resetPasswordValue" class="form-control" required />
            </div>

            <div *ngIf="modalError" class="modal-error">
              {{ modalError }}
            </div>

            <div class="modal-actions">
              <button type="button" class="btn btn-secondary" (click)="closeModals()">Cancel</button>
              <button type="submit" class="btn btn-primary" [disabled]="!resetPasswordValue">Reset Password</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .users-page {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }

    .page-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 1rem;

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
        .filter-select {
          padding: 0.45rem 0.65rem;
          font-size: 0.8rem;
          border-radius: var(--radius-sm);
          min-width: 150px;
        }
      }
    }

    .user-cell {
      display: flex;
      align-items: center;
      gap: 0.65rem;

      .user-avatar-sm {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: #e2e8f0;
        color: #334155;
        font-size: 0.7rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .user-username {
        font-weight: 600;
        color: #0f172a;
      }
    }

    .actions-group {
      display: flex;
      gap: 0.35rem;
    }

    .modal-actions {
      display: flex;
      justify-content: flex-end;
      gap: 0.75rem;
      margin-top: 1.5rem;
    }

    .modal-error {
      padding: 0.65rem;
      background: var(--danger-bg);
      border: 1px solid var(--danger-border);
      border-radius: var(--radius-sm);
      color: var(--danger-text);
      font-size: 0.8rem;
      margin-top: 0.75rem;
    }
  `],
})
export class UsersComponent implements OnInit {
  private userService = inject(UserService);
  private changeDetector = inject(ChangeDetectorRef);

  users: UserListItem[] = [];
  searchQuery = '';
  roleFilter = '';

  showCreateModal = false;
  showEditModal = false;
  showPasswordModal = false;
  editingUser: UserListItem | null = null;
  modalError = '';

  newUsername = '';
  newEmail = '';
  newPassword = '';
  newRole: Role = 'OPERATOR';

  editEmail = '';
  editRole: Role = 'OPERATOR';

  resetPasswordValue = '';

  ngOnInit(): void {
    this.loadUsers();
  }

  loadUsers(): void {
    this.userService.getUsers().subscribe({
      next: (data) => {
        this.users = data;
        this.changeDetector.markForCheck();
      },
    });
  }

  filteredUsers(): UserListItem[] {
    return this.users.filter((u) => {
      const matchSearch =
        !this.searchQuery ||
        u.username.toLowerCase().includes(this.searchQuery.toLowerCase()) ||
        u.email.toLowerCase().includes(this.searchQuery.toLowerCase());
      const matchRole = !this.roleFilter || u.role === this.roleFilter;
      return matchSearch && matchRole;
    });
  }

  openCreateModal(): void {
    this.modalError = '';
    this.newUsername = '';
    this.newEmail = '';
    this.newPassword = '';
    this.newRole = 'OPERATOR';
    this.showCreateModal = true;
  }

  openEditModal(user: UserListItem): void {
    this.modalError = '';
    this.editingUser = user;
    this.editEmail = user.email;
    this.editRole = user.role;
    this.showEditModal = true;
  }

  openPasswordModal(user: UserListItem): void {
    this.modalError = '';
    this.editingUser = user;
    this.resetPasswordValue = '';
    this.showPasswordModal = true;
  }

  closeModals(): void {
    this.showCreateModal = false;
    this.showEditModal = false;
    this.showPasswordModal = false;
    this.editingUser = null;
    this.modalError = '';
  }

  onCreateUser(): void {
    this.modalError = '';
    const payload: CreateUserPayload = {
      username: this.newUsername,
      email: this.newEmail,
      password: this.newPassword,
      role: this.newRole,
    };

    this.userService.createUser(payload).subscribe({
      next: () => {
        this.closeModals();
        this.loadUsers();
      },
      error: (err) => {
        this.modalError = err.error?.detail || JSON.stringify(err.error);
      },
    });
  }

  onUpdateUser(): void {
    if (!this.editingUser) return;
    this.modalError = '';
    this.userService.updateUser(this.editingUser.id, { email: this.editEmail, role: this.editRole }).subscribe({
      next: () => {
        this.closeModals();
        this.loadUsers();
      },
      error: (err) => {
        this.modalError = err.error?.detail || JSON.stringify(err.error);
      },
    });
  }

  onResetPassword(): void {
    if (!this.editingUser) return;
    this.modalError = '';
    this.userService.setPassword(this.editingUser.id, this.resetPasswordValue).subscribe({
      next: () => {
        this.closeModals();
      },
      error: (err) => {
        this.modalError = err.error?.detail || JSON.stringify(err.error);
      },
    });
  }

  toggleActive(user: UserListItem): void {
    const op = user.is_active
      ? this.userService.deactivateUser(user.id)
      : this.userService.activateUser(user.id);

    op.subscribe({
      next: () => {
        this.loadUsers();
      },
    });
  }
}
