import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { DashboardService } from '../../core/services/dashboard.service';
import { OverviewComponent } from './overview.component';

describe('OverviewComponent', () => {
  const summary = {
    total: 4,
    healthy: 1,
    warning: 1,
    high_risk: 1,
    anomalous: 1,
    not_scored: 1,
    data_until: null,
    top_critical: [],
  };
  const activity = {
    results: [{
      id: 10,
      drive_identifier: 'SN-001',
      drive_name: 'Drive SN-001',
      kind: 'Failure risk' as const,
      outcome: 'HIGH',
      score: 0.82,
      created_at: '2026-11-20T10:00:00Z',
    }],
  };

  async function createComponent(dashboardService: Partial<DashboardService>) {
    await TestBed.configureTestingModule({
      imports: [OverviewComponent],
      providers: [
        provideRouter([]),
        { provide: DashboardService, useValue: dashboardService },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => false } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(OverviewComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return fixture;
  }

  it('renders fleet KPIs, recent drive activity and last refresh time', async () => {
    const fixture = await createComponent({
      getSummary: () => of(summary),
      getRecentActivity: () => of(activity),
    });
    const element = fixture.nativeElement as HTMLElement;

    expect(element.querySelectorAll('.kpi-grid .kpi-card').length).toBe(6);
    expect(element.textContent).toContain('TOTAL MONITORED DRIVES');
    expect(element.textContent).toContain('SN-001');
    expect(element.textContent).toContain('HIGH');
    expect(element.textContent).toContain('Last updated');
  });

  it('shows a recoverable dashboard error when fleet statistics fail', async () => {
    const fixture = await createComponent({
      getSummary: () => throwError(() => new Error('unavailable')),
      getRecentActivity: () => of({ results: [] }),
    });

    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')?.textContent)
      .toContain('Dashboard statistics could not be loaded.');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Try again');
  });

  it('shows a useful empty state when no drives or predictions exist', async () => {
    const fixture = await createComponent({
      getSummary: () => of({ ...summary, total: 0, healthy: 0, warning: 0, high_risk: 0, anomalous: 0, not_scored: 0 }),
      getRecentActivity: () => of({ results: [] }),
    });

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No drives are registered yet.');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No prediction runs have been recorded yet.');
  });
});
