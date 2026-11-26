import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap, catchError, throwError, of, finalize, shareReplay } from 'rxjs';
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
  private profileRequest: Observable<User | null> | null = null;
  readonly currentUser = this.currentUserSignal.asReadonly();
  readonly isLoggedIn = computed(() => !!this.currentUserSignal());
  readonly userRole = computed(() => this.currentUserSignal()?.role ?? null);
  readonly isSysAdmin = computed(() => this.userRole() === 'SYSADMIN');
  readonly isITProOrSysAdmin = computed(() => this.userRole() === 'SYSADMIN' || this.userRole() === 'IT_PRO');
  readonly isOperator = computed(() => this.userRole() === 'OPERATOR');

  ensureProfileLoaded(): Observable<User | null> {
    const user = this.currentUserSignal();
    if (user) return of(user);
    if (!this.getAccessToken()) return of(null);

    if (!this.profileRequest) {
      this.profileRequest = this.fetchMe().pipe(
        catchError(() => {
          this.logout();
          return of(null);
        }),
        finalize(() => { this.profileRequest = null; }),
        shareReplay({ bufferSize: 1, refCount: false }),
      );
    }
    return this.profileRequest;
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
    const refresh = this.getRefreshToken();
    if (!refresh) {
      this.clearTokens();
      this.router.navigate(['/login']);
      return;
    }

    // Keep the access token available until the interceptor sends this request.
    // Local logout always completes, even if the server cannot revoke the token.
    this.http.post<void>(`${environment.apiUrl}/auth/logout/`, { refresh }).pipe(
      catchError(() => of(undefined)),
      finalize(() => {
        this.clearTokens();
        this.router.navigate(['/login']);
      }),
    ).subscribe();
  }
}
