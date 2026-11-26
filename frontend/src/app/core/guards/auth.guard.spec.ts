import { TestBed } from '@angular/core/testing';
import { provideRouter, UrlTree } from '@angular/router';
import { Observable, Subject, firstValueFrom } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { authGuard, itProOrSysadminGuard, sysadminGuard } from './auth.guard';

describe('role route guards', () => {
  it('waits for the current-user request before allowing a protected route after refresh', async () => {
    const profile = new Subject<any>();
    await TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { getAccessToken: () => 'present', ensureProfileLoaded: () => profile } },
      ],
    }).compileComponents();

    const result = TestBed.runInInjectionContext(() =>
      authGuard({} as any, { url: '/overview' } as any),
    ) as Observable<boolean | UrlTree>;
    const decision = firstValueFrom(result);
    profile.next({ role: 'OPERATOR' });
    profile.complete();

    expect(await decision).toBe(true);
  });

  it('waits for profile initialization before allowing an IT_PRO route', async () => {
    const profile = new Subject<any>();
    await TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: { ensureProfileLoaded: () => profile } }],
    }).compileComponents();

    const result = TestBed.runInInjectionContext(() =>
      itProOrSysadminGuard({} as any, { url: '/upload' } as any),
    ) as Observable<boolean | UrlTree>;
    const decision = firstValueFrom(result);
    profile.next({ role: 'IT_PRO' });
    profile.complete();

    expect(await decision).toBe(true);
  });

  it('waits for profile initialization and denies non-admins from admin routes', async () => {
    const profile = new Subject<any>();
    await TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: { ensureProfileLoaded: () => profile } }],
    }).compileComponents();

    const result = TestBed.runInInjectionContext(() =>
      sysadminGuard({} as any, { url: '/users' } as any),
    ) as Observable<boolean | UrlTree>;
    const decision = firstValueFrom(result);
    profile.next({ role: 'OPERATOR' });
    profile.complete();

    expect(await decision).toBeInstanceOf(UrlTree);
  });

  it('allows SYSADMIN after profile resolution and denies OPERATOR from write routes', async () => {
    const adminProfile = new Subject<any>();
    await TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: { ensureProfileLoaded: () => adminProfile } }],
    }).compileComponents();
    const adminResult = TestBed.runInInjectionContext(() =>
      sysadminGuard({} as any, { url: '/users' } as any),
    ) as Observable<boolean | UrlTree>;
    const adminDecision = firstValueFrom(adminResult);
    adminProfile.next({ role: 'SYSADMIN' });
    adminProfile.complete();
    expect(await adminDecision).toBe(true);

    TestBed.resetTestingModule();
    const operatorProfile = new Subject<any>();
    await TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: { ensureProfileLoaded: () => operatorProfile } }],
    }).compileComponents();
    const operatorResult = TestBed.runInInjectionContext(() =>
      itProOrSysadminGuard({} as any, { url: '/predictions' } as any),
    ) as Observable<boolean | UrlTree>;
    const operatorDecision = firstValueFrom(operatorResult);
    operatorProfile.next({ role: 'OPERATOR' });
    operatorProfile.complete();
    expect(await operatorDecision).toBeInstanceOf(UrlTree);
  });
});
