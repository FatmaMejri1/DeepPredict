import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { DashboardService } from '../../core/services/dashboard.service';
import { DashboardFilters } from '../../core/models/dashboard.models';
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
    fixture.destroy();
  });

  it('shows a recoverable dashboard error when fleet statistics fail', async () => {
    const fixture = await createComponent({
      getSummary: () => throwError(() => new Error('unavailable')),
      getRecentActivity: () => of({ results: [] }),
    });

    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')?.textContent)
      .toContain('Dashboard statistics could not be loaded.');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Try again');
    fixture.destroy();
  });

  it('shows a useful empty state when no drives or predictions exist', async () => {
    const fixture = await createComponent({
      getSummary: () => of({ ...summary, total: 0, healthy: 0, warning: 0, high_risk: 0, anomalous: 0, not_scored: 0 }),
      getRecentActivity: () => of({ results: [] }),
    });

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No drives are registered yet.');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No prediction runs have been recorded yet.');
    fixture.destroy();
  });

  it('sends selected dashboard filters to both endpoints and clears them on reset', async () => {
    const summaryRequests: DashboardFilters[] = [];
    const activityRequests: DashboardFilters[] = [];
    const fixture = await createComponent({
      getSummary: (filters?: DashboardFilters) => {
        summaryRequests.push(filters ?? {});
        return of(filters?.status
          ? { ...summary, total: 1, healthy: 0, warning: 0, high_risk: 1 }
          : summary);
      },
      getRecentActivity: (filters?: DashboardFilters) => {
        activityRequests.push(filters ?? {});
        return of(activity);
      },
    });
    const element = fixture.nativeElement as HTMLElement;
    const statusFilter = element.querySelector('#dashboard-status-filter') as HTMLSelectElement;

    statusFilter.value = 'HIGH_RISK';
    statusFilter.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(summaryRequests.at(-1)).toEqual({ status: 'HIGH_RISK', risk_level: '', is_anomalous: '' });
    expect(activityRequests.at(-1)).toEqual({ status: 'HIGH_RISK', risk_level: '', is_anomalous: '' });
    expect(element.querySelector('.kpi-card.total .kpi-value')?.textContent?.trim()).toBe('1');
    expect(element.querySelector('.kpi-card.high-risk .kpi-value')?.textContent?.trim()).toBe('1');

    (element.querySelector('.clear-filters') as HTMLButtonElement).click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(summaryRequests.at(-1)).toEqual({ status: '', risk_level: '', is_anomalous: '' });
    expect(activityRequests.at(-1)).toEqual({ status: '', risk_level: '', is_anomalous: '' });
    expect(element.querySelector('.kpi-card.total .kpi-value')?.textContent?.trim()).toBe('4');
    fixture.destroy();
  });

  it('shows a filtered empty state when the selected criteria match no drives', async () => {
    const fixture = await createComponent({
      getSummary: () => of({ ...summary, total: 0, healthy: 0, warning: 0, high_risk: 0, anomalous: 0, not_scored: 0 }),
      getRecentActivity: () => of({ results: [] }),
    });
    const element = fixture.nativeElement as HTMLElement;
    const statusFilter = element.querySelector('#dashboard-status-filter') as HTMLSelectElement;

    statusFilter.value = 'WARNING';
    statusFilter.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(element.textContent).toContain('No drives match the selected filters.');
    expect(element.textContent).toContain('No prediction runs match the selected filters.');
    expect(element.textContent).not.toContain('No drives are registered yet.');
    fixture.destroy();
  });

  it('shows loading and recovers from a filtered request error using retry', async () => {
    let summaryCalls = 0;
    const filteredSummary = new Subject<typeof summary>();
    const fixture = await createComponent({
      getSummary: (filters?: DashboardFilters) => {
        summaryCalls += 1;
        if (filters?.status && summaryCalls === 2) return filteredSummary.asObservable();
        return of(summary);
      },
      getRecentActivity: () => of(activity),
    });
    const element = fixture.nativeElement as HTMLElement;
    const statusFilter = element.querySelector('#dashboard-status-filter') as HTMLSelectElement;

    statusFilter.value = 'HIGH_RISK';
    statusFilter.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    expect(element.textContent).toContain('Loading fleet statistics…');
    filteredSummary.error(new Error('unavailable'));
    await fixture.whenStable();
    fixture.detectChanges();

    expect(element.querySelector('[role="alert"]')?.textContent).toContain('Dashboard statistics could not be loaded.');
    expect(element.querySelector('.kpi-grid')).toBeNull();
    (element.querySelector('.error-state button') as HTMLButtonElement).click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(summaryCalls).toBe(3);
    expect(element.querySelector('.kpi-grid')).not.toBeNull();
    fixture.destroy();
  });
});
