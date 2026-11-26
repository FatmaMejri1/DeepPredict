import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';
import { AlertPage } from '../../../core/models/alert.models';
import { AlertService } from '../../../core/services/alert.service';
import { routes } from '../../../app.routes';
import { AlertDetailComponent } from '../alert-detail/alert-detail.component';
import { AlertsListComponent } from './alerts-list.component';

const page = (results: any[] = [], count = results.length): AlertPage => ({ count, next: null, previous: null, results });

describe('AlertsListComponent', () => {
  async function render(getAlerts: ReturnType<typeof vi.fn>) {
    await TestBed.configureTestingModule({
      imports: [AlertsListComponent],
      providers: [provideRouter([]), { provide: AlertService, useValue: { getAlerts } }],
    }).compileComponents();
    const fixture = TestBed.createComponent(AlertsListComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return fixture;
  }

  it('shows empty and error states and retries after a request error', async () => {
    const getAlerts = vi.fn().mockReturnValue(of(page()));
    const fixture = await render(getAlerts);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No alerts found');
    expect(getAlerts).toHaveBeenCalledTimes(1);

    getAlerts.mockReturnValueOnce(throwError(() => new Error('offline')));
    fixture.componentInstance.loadAlerts();
    await fixture.whenStable();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')?.textContent).toContain('Alerts could not be loaded');

    getAlerts.mockReturnValueOnce(of(page()));
    (fixture.nativeElement.querySelector('[role="alert"] button') as HTMLButtonElement).click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No alerts found');
    fixture.destroy();
  });

  it('shows a loading state while the list request is pending', async () => {
    const response = new Subject<AlertPage>();
    const fixture = await render(vi.fn().mockReturnValue(response));
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="status"]')?.textContent).toContain('Loading alerts');
    response.next(page());
    await fixture.whenStable(); fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No alerts found');
    fixture.destroy();
  });

  it('sends selected filters, supports pagination and clears filters', async () => {
    const rows = [{
      id: 'a-1', alert_type: 'ANOMALY', severity: 'HIGH', status: 'OPEN',
      resource: { id: 'drive-1', name: 'Drive A', identifier: 'SERIAL-A' },
      first_seen_at: '2026-01-01T00:00:00Z', last_seen_at: '2026-01-02T00:00:00Z', occurrence_count: 2,
    }];
    const getAlerts = vi.fn().mockReturnValue(of({ ...page(rows, 45), next: '/api/alerts/?page=2' }));
    const fixture = await render(getAlerts);
    const selects = fixture.nativeElement.querySelectorAll('select');
    selects[0].value = 'OPEN'; selects[0].dispatchEvent(new Event('change'));
    selects[1].value = 'ANOMALY'; selects[1].dispatchEvent(new Event('change'));
    selects[2].value = 'HIGH'; selects[2].dispatchEvent(new Event('change'));
    const resourceFilter = fixture.nativeElement.querySelector('.resource-filter input') as HTMLInputElement;
    resourceFilter.value = 'drive-1'; resourceFilter.dispatchEvent(new Event('input'));
    (fixture.nativeElement.querySelector('.filter-actions .btn-primary') as HTMLButtonElement).click();
    await fixture.whenStable(); fixture.detectChanges();
    expect(getAlerts.mock.calls.at(-1)?.[0]).toEqual({ status: 'OPEN', alert_type: 'ANOMALY', severity: 'HIGH', resource: 'drive-1' });
    expect(getAlerts.mock.calls.at(-1)?.slice(1)).toEqual([1, 20]);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Drive A');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Anomaly');
    expect((fixture.nativeElement.querySelector('.resource-link') as HTMLAnchorElement).getAttribute('href')).toBe('/drives/drive-1');

    (fixture.nativeElement.querySelector('.pagination button:last-child') as HTMLButtonElement).click();
    await fixture.whenStable(); fixture.detectChanges();
    expect(getAlerts.mock.calls.at(-1)?.[1]).toBe(2);
    expect(getAlerts.mock.calls.at(-1)?.[2]).toBe(20);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Page 2 of 3');

    (fixture.nativeElement.querySelector('.filter-actions .btn-secondary') as HTMLButtonElement).click();
    await fixture.whenStable(); fixture.detectChanges();
    expect(getAlerts.mock.calls.at(-1)?.[0]).toEqual({ status: '', alert_type: '', severity: '', resource: '' });
    expect(getAlerts.mock.calls.at(-1)?.slice(1)).toEqual([1, 20]);
    fixture.destroy();
  });

  it('declares the authenticated inbox and alert-detail routes', () => {
    const shellRoutes = routes.find((route) => route.path === '');
    const alertListRoute = shellRoutes?.children?.find((route) => route.path === 'alerts');
    const alertDetailRoute = shellRoutes?.children?.find((route) => route.path === 'alerts/:id');

    expect(shellRoutes?.canActivate?.length).toBeGreaterThan(0);
    expect(alertListRoute?.component).toBe(AlertsListComponent);
    expect(alertDetailRoute?.component).toBe(AlertDetailComponent);
  });
});
