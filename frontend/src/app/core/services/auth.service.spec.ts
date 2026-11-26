import { TestBed } from '@angular/core/testing';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';
import { authInterceptor } from '../interceptors/auth.interceptor';

describe('AuthService profile initialization', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('dp_access_token', 'test-access-token');
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: Router, useValue: { navigate: vi.fn().mockResolvedValue(true) } },
      ],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    localStorage.clear();
  });

  it('shares and waits for the current-user request before exposing the role', async () => {
    let resolvedRole: string | null = null;
    service.ensureProfileLoaded().subscribe((user) => { resolvedRole = user?.role ?? null; });

    const profileRequest = http.expectOne('/api/auth/me/');
    profileRequest.flush({
      id: '8debe1a7-c947-4a88-a915-226eaf7db895',
      username: 'dedicated-admin',
      email: 'admin@example.test',
      role: 'SYSADMIN',
      is_active: true,
    });

    expect(resolvedRole).toBe('SYSADMIN');
    expect(service.isSysAdmin()).toBe(true);
  });

  it('posts the refresh token with the current access token and clears state after success', () => {
    service.setTokens('logout-access-token', 'logout-refresh-token');
    service.fetchMe().subscribe();
    http.expectOne('/api/auth/me/').flush({
      id: '8debe1a7-c947-4a88-a915-226eaf7db895',
      username: 'dedicated-admin',
      email: 'admin@example.test',
      role: 'SYSADMIN',
      is_active: true,
    });

    service.logout();

    const request = http.expectOne('/api/auth/logout/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ refresh: 'logout-refresh-token' });
    expect(request.request.headers.get('Authorization')).toBe('Bearer logout-access-token');
    request.flush(null, { status: 204, statusText: 'No Content' });

    expect(localStorage.getItem('dp_access_token')).toBeNull();
    expect(localStorage.getItem('dp_refresh_token')).toBeNull();
    expect(service.currentUser()).toBeNull();
  });

  it('clears local authentication when the backend rejects logout without refreshing', () => {
    service.setTokens('logout-access-token', 'invalid-refresh-token');
    service.fetchMe().subscribe();
    http.expectOne('/api/auth/me/').flush({
      id: '8debe1a7-c947-4a88-a915-226eaf7db895',
      username: 'dedicated-admin',
      email: 'admin@example.test',
      role: 'SYSADMIN',
      is_active: true,
    });

    service.logout();
    http.expectOne('/api/auth/logout/').flush(
      { detail: 'Invalid token' },
      { status: 401, statusText: 'Unauthorized' },
    );

    http.expectNone('/api/auth/refresh/');
    expect(localStorage.getItem('dp_access_token')).toBeNull();
    expect(localStorage.getItem('dp_refresh_token')).toBeNull();
    expect(service.currentUser()).toBeNull();
  });

  it('completes local logout without an API request when no refresh token exists', () => {
    service.setTokens('access-only-token', 'temporary-refresh-token');
    service.fetchMe().subscribe();
    http.expectOne('/api/auth/me/').flush({
      id: '8debe1a7-c947-4a88-a915-226eaf7db895',
      username: 'dedicated-admin',
      email: 'admin@example.test',
      role: 'SYSADMIN',
      is_active: true,
    });
    localStorage.removeItem('dp_refresh_token');

    service.logout();

    http.expectNone('/api/auth/logout/');
    expect(localStorage.getItem('dp_access_token')).toBeNull();
    expect(localStorage.getItem('dp_refresh_token')).toBeNull();
    expect(service.currentUser()).toBeNull();
  });
});
