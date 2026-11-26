import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { signal } from '@angular/core';
import { BehaviorSubject, of, throwError } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { AlertService } from '../../core/services/alert.service';
import { DashboardService } from '../../core/services/dashboard.service';
import { Role, User } from '../../core/models/auth.models';
import { HeaderComponent } from './header.component';

describe('HeaderComponent', () => {
  async function render(
    healthRequest: () => ReturnType<DashboardService['getInferenceHealth']>,
    role: Role | null = 'IT_PRO',
    unreadCount: number | null = 0,
  ) {
    const currentUser = signal<User | null>(role ? {
      id: `user-${role}`,
      username: `user-${role.toLowerCase()}`,
      email: `${role.toLowerCase()}@example.test`,
      role,
      is_active: true,
    } : null);
    const unreadCountSubject = new BehaviorSubject<number | null>(unreadCount);
    let refreshResult = unreadCount;
    const refreshUnreadCount = vi.fn(() => {
      unreadCountSubject.next(refreshResult);
      return of(refreshResult);
    });
    await TestBed.configureTestingModule({
      imports: [HeaderComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { currentUser: currentUser.asReadonly() } },
        { provide: DashboardService, useValue: { getInferenceHealth: healthRequest } },
        {
          provide: AlertService,
          useValue: {
            unreadCount$: unreadCountSubject.asObservable(),
            refreshUnreadCount,
            clearUnreadCount: () => unreadCountSubject.next(null),
          },
        },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(HeaderComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return {
      fixture,
      currentUser,
      unreadCountSubject,
      refreshUnreadCount,
      setRefreshResult: (count: number | null) => { refreshResult = count; },
    };
  }

  it('shows online status and the model version from the health response', async () => {
    const { fixture } = await render(() => of({
      status: 'online',
      model_version: 'gru-ae-v1',
      checked_at: '2026-11-20T10:00:00Z',
    }));
    const status = (fixture.nativeElement as HTMLElement).querySelector('.system-status-indicator');

    expect(status?.classList.contains('is-online')).toBe(true);
    expect(status?.textContent).toContain('Predictive Engine Online');
    expect(status?.textContent).toContain('gru-ae-v1');
    fixture.destroy();
  });

  it('shows offline status when the health request fails', async () => {
    const { fixture } = await render(() => throwError(() => new Error('offline')));
    const status = (fixture.nativeElement as HTMLElement).querySelector('.system-status-indicator');

    expect(status?.classList.contains('is-offline')).toBe(true);
    expect(status?.textContent).toContain('Predictive Engine Offline');
    expect(status?.textContent).toContain('Health check unavailable');
    fixture.destroy();
  });

  it('shows the open-alert badge and links to the alerts inbox', async () => {
    const { fixture } = await render(() => of({ status: 'online', model_version: 'v1', checked_at: '' }), 'IT_PRO', 4);
    const link = (fixture.nativeElement as HTMLElement).querySelector('.notification-link');
    expect(link?.getAttribute('href')).toBe('/alerts');
    expect(link?.getAttribute('aria-label')).toBe('Alerts, 4 open alerts');
    expect(link?.getAttribute('title')).toBe('Alerts, 4 open alerts');
    expect(link?.querySelector('.screen-reader-only')?.textContent?.trim()).toBe('4 open alerts');
    expect(link?.querySelector('.notification-count')?.textContent?.trim()).toBe('4');
    fixture.destroy();
  });

  it('hides the alert badge when the count is zero or unavailable', async () => {
    const { fixture: zeroFixture } = await render(() => of({ status: 'online', model_version: 'v1', checked_at: '' }), 'SYSADMIN', 0);
    const link = (zeroFixture.nativeElement as HTMLElement).querySelector('.notification-link');
    expect(link?.querySelector('.notification-count')).toBeNull();
    expect(link?.getAttribute('aria-label')).toBe('Alerts, no open alerts');
    expect(link?.querySelector('.screen-reader-only')?.textContent?.trim()).toBe('No open alerts');
    zeroFixture.destroy();
  });

  it('does not display a badge when the unread count is unavailable', async () => {
    const { fixture } = await render(() => of({ status: 'online', model_version: 'v1', checked_at: '' }), 'OPERATOR', null);
    const link = (fixture.nativeElement as HTMLElement).querySelector('.notification-link');
    expect(link?.querySelector('.notification-count')).toBeNull();
    expect(link?.getAttribute('aria-label')).toBe('Alerts, open-alert count unavailable');
    expect(link?.querySelector('.screen-reader-only')?.textContent?.trim()).toBe('Open alert count unavailable');
    fixture.destroy();
  });

  it.each(['SYSADMIN', 'IT_PRO', 'OPERATOR'] as const)('shows the bell for authenticated role %s', async (role) => {
    const { fixture, refreshUnreadCount } = await render(
      () => of({ status: 'online', model_version: 'v1', checked_at: '' }), role, 2,
    );
    expect((fixture.nativeElement as HTMLElement).querySelector('.notification-link')).not.toBeNull();
    expect(refreshUnreadCount).toHaveBeenCalledTimes(1);
    fixture.destroy();
  });

  it('updates the badge as the shared unread count emits and caps the visible value at 99+', async () => {
    const { fixture, unreadCountSubject } = await render(
      () => of({ status: 'online', model_version: 'v1', checked_at: '' }), 'IT_PRO', 128,
    );
    const element = fixture.nativeElement as HTMLElement;
    const link = element.querySelector('.notification-link') as HTMLAnchorElement;
    expect(link.querySelector('.notification-count')?.textContent?.trim()).toBe('99+');
    expect(link.getAttribute('aria-label')).toBe('Alerts, 128 open alerts');

    unreadCountSubject.next(1);
    fixture.detectChanges();
    expect(link.querySelector('.notification-count')?.textContent?.trim()).toBe('1');
    expect(link.getAttribute('aria-label')).toBe('Alerts, 1 open alert');

    unreadCountSubject.next(0);
    fixture.detectChanges();
    expect(link.querySelector('.notification-count')).toBeNull();
    fixture.destroy();
  });

  it('clears the previous session count and refreshes for the next authenticated user', async () => {
    const { fixture, currentUser, unreadCountSubject, refreshUnreadCount, setRefreshResult } = await render(
      () => of({ status: 'online', model_version: 'v1', checked_at: '' }), 'IT_PRO', 7,
    );
    expect((fixture.nativeElement as HTMLElement).querySelector('.notification-count')?.textContent?.trim()).toBe('7');

    currentUser.set(null);
    fixture.detectChanges();
    expect(unreadCountSubject.value).toBeNull();
    expect((fixture.nativeElement as HTMLElement).querySelector('.notification-link')).toBeNull();

    setRefreshResult(1);
    currentUser.set({
      id: 'new-user', username: 'new-user', email: 'new@example.test', role: 'SYSADMIN', is_active: true,
    });
    fixture.detectChanges();
    expect(refreshUnreadCount).toHaveBeenCalledTimes(2);
    expect((fixture.nativeElement as HTMLElement).querySelector('.notification-count')?.textContent?.trim()).toBe('1');
    fixture.destroy();
  });

  it('keeps the shell usable when the initial unread count is unavailable and supports keyboard focus', async () => {
    const { fixture } = await render(
      () => of({ status: 'online', model_version: 'v1', checked_at: '' }), 'IT_PRO', null,
    );
    const element = fixture.nativeElement as HTMLElement;
    const link = element.querySelector('.notification-link') as HTMLAnchorElement;
    expect(element.querySelector('.system-status-indicator')).not.toBeNull();
    expect(link.getAttribute('href')).toBe('/alerts');
    expect(link.tabIndex).toBe(0);
    link.focus();
    expect(document.activeElement).toBe(link);
    expect(link.getAttribute('aria-label')).toBe('Alerts, open-alert count unavailable');
    fixture.destroy();
  });

  it('does not show the bell when there is no authenticated user', async () => {
    const { fixture, refreshUnreadCount } = await render(
      () => of({ status: 'online', model_version: 'v1', checked_at: '' }), null, 5,
    );
    expect((fixture.nativeElement as HTMLElement).querySelector('.notification-link')).toBeNull();
    expect(refreshUnreadCount).not.toHaveBeenCalled();
    fixture.destroy();
  });
});
