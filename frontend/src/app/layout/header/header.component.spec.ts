import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { DashboardService } from '../../core/services/dashboard.service';
import { HeaderComponent } from './header.component';

describe('HeaderComponent AI service status', () => {
  async function render(healthRequest: () => ReturnType<DashboardService['getInferenceHealth']>) {
    await TestBed.configureTestingModule({
      imports: [HeaderComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { currentUser: () => null } },
        { provide: DashboardService, useValue: { getInferenceHealth: healthRequest } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(HeaderComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return fixture;
  }

  it('shows online status and the model version from the health response', async () => {
    const fixture = await render(() => of({
      status: 'online',
      model_version: 'gru-ae-v1',
      checked_at: '2026-11-20T10:00:00Z',
    }));
    const status = (fixture.nativeElement as HTMLElement).querySelector('.system-status-indicator');

    expect(status?.classList.contains('is-online')).toBe(true);
    expect(status?.textContent).toContain('Predictive Engine Online');
    expect(status?.textContent).toContain('gru-ae-v1');
  });

  it('shows offline status when the health request fails', async () => {
    const fixture = await render(() => throwError(() => new Error('offline')));
    const status = (fixture.nativeElement as HTMLElement).querySelector('.system-status-indicator');

    expect(status?.classList.contains('is-offline')).toBe(true);
    expect(status?.textContent).toContain('Predictive Engine Offline');
    expect(status?.textContent).toContain('Health check unavailable');
  });
});
