import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap, catchError, throwError, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ChangePasswordRequest, LoginResponse, Role, User } from '../models/auth.models';

const ACCESS_KEY = 'dp_access_token';
const REFRESH_KEY = 'dp_refresh_token';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);

  private currentUserSignal = signal<User | null>(null);
  readonly currentUser = this.currentUserSignal.asReadonly();
  readonly isLoggedIn = computed(() => !!this.currentUserSignal());
  readonly userRole = computed(() => this.currentUserSignal()?.role ?? null);
  readonly isSysAdmin = computed(() => this.userRole() === 'SYSADMIN');
  readonly isITProOrSysAdmin = computed(() => this.userRole() === 'SYSADMIN' || this.userRole() === 'IT_PRO');
  readonly isOperator = computed(() => this.userRole() === 'OPERATOR');

  constructor() {
    this.initUser();
  }

  private initUser(): void {
    const token = this.getAccessToken();
    if (token) {
      this.fetchMe().subscribe({
        error: () => this.logout(),
      });
    }
  }

  getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_KEY);
  }

  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_KEY);
  }

  setTokens(access: string, refresh: string): void {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  }

  clearTokens(): void {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    this.currentUserSignal.set(null);
  }

  login(credentials: { username: string; password: string }): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${environment.apiUrl}/auth/login/`, credentials).pipe(
      tap((resp) => {
        this.setTokens(resp.access, resp.refresh);
      })
    );
  }

  fetchMe(): Observable<User> {
    return this.http.get<User>(`${environment.apiUrl}/auth/me/`).pipe(
      tap((user) => {
        this.currentUserSignal.set(user);
      })
    );
  }

  refreshToken(): Observable<{ access: string }> {
    const refresh = this.getRefreshToken();
    if (!refresh) {
      return throwError(() => new Error('No refresh token available'));
    }
    return this.http.post<{ access: string }>(`${environment.apiUrl}/auth/refresh/`, { refresh }).pipe(
      tap((resp) => {
        localStorage.setItem(ACCESS_KEY, resp.access);
      })
    );
  }

  changePassword(payload: ChangePasswordRequest): Observable<any> {
    return this.http.post(`${environment.apiUrl}/auth/change-password/`, payload);
  }

  logout(): void {
    this.clearTokens();
    this.router.navigate(['/login']);
  }
}
