import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { Drive } from '../../../core/models/drive.models';
import { AuthService } from '../../../core/services/auth.service';
import { DriveQueryParams, DriveService } from '../../../core/services/drive.service';
import { DriveListComponent } from './drive-list.component';
import { routes } from '../../../app.routes';

describe('DriveListComponent', () => {
  const unscoredDrive: Drive = {
    id: '00000000-0000-0000-0000-000000000123',
    name: 'Unscored test drive',
    identifier: 'UNSCORED-123',
    model: 'Test model',
    vendor: 'Test vendor',
    datacenter: 'Test DC',
    status: 'HEALTHY',
    risk_level: null,
    risk_score: null,
    scored_until: null,
    is_anomalous: false,
    anomaly_evaluated: false,
    last_reading: null,
  };

  async function createComponent(highRiskOnly = false) {
    const requests: (DriveQueryParams | undefined)[] = [];
    const driveService = {
      getDrives: (params?: DriveQueryParams) => {
        requests.push(params);
        return of({ count: 1, next: null, previous: null, results: [unscoredDrive] });
      },
    };
    await TestBed.configureTestingModule({
      imports: [DriveListComponent],
      providers: [
        provideRouter([]),
        { provide: DriveService, useValue: driveService },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => false } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(DriveListComponent);
    fixture.componentInstance.highRiskOnly = highRiskOnly;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return { fixture, requests };
  }

  it('sends selected filters, ordering and page to the drives API', async () => {
    const { fixture, requests } = await createComponent();
    const component = fixture.componentInstance;
    component.search = 'SN-7';
    component.statusFilter = 'HIGH_RISK';
    component.riskFilter = 'CRITICAL';
    component.anomalyFilter = 'true';
    component.ordering = 'risk_score';

    component.loadDrives(2);

    expect(requests.at(-1)).toEqual({
      search: 'SN-7',
      status: 'HIGH_RISK',
      risk_level: 'CRITICAL',
      is_anomalous: 'true',
      ordering: 'risk_score',
      page: 2,
      page_size: 20,
    });
  });

  it('loads the dedicated high-risk view using only the existing status filter', async () => {
    const { fixture, requests } = await createComponent(true);
    const component = fixture.componentInstance;

    expect(requests[0]?.status).toBe('HIGH_RISK');
    expect(requests[0]?.risk_level).toBe('');
    expect(requests[0]?.is_anomalous).toBe('');
    expect((fixture.nativeElement as HTMLElement).querySelector('h1')?.textContent).toContain('High-Risk Drives');

    component.statusFilter = 'HEALTHY';
    component.riskFilter = 'HIGH';
    component.anomalyFilter = 'true';
    component.loadDrives(2);

    expect(requests.at(-1)?.status).toBe('HIGH_RISK');
    expect(requests.at(-1)?.risk_level).toBe('HIGH');
    expect(requests.at(-1)?.is_anomalous).toBe('true');
  });

  it('registers the high-risk route as an authenticated drive-list view', () => {
    const shell = routes.find((route) => route.path === '');
    const highRiskRoute = shell?.children?.find((route) => route.path === 'high-risk-drives');

    expect(highRiskRoute?.component).toBe(DriveListComponent);
    expect(highRiskRoute?.data).toEqual({ highRiskOnly: true });
    expect(shell?.canActivate).toBeDefined();
  });

  it('renders an unscored drive as not scored instead of a zero risk score', async () => {
    const { fixture } = await createComponent();
    const element = fixture.nativeElement as HTMLElement;

    expect(element.textContent).toContain('UNSCORED-123');
    expect(element.textContent).toContain('NOT SCORED');
    expect(element.textContent).toContain('NOT EVALUATED');
    expect(element.textContent).not.toContain('0.000');
  });

  it('shows a retryable inventory error instead of an empty-results message on API failure', async () => {
    await TestBed.configureTestingModule({
      imports: [DriveListComponent],
      providers: [
        provideRouter([]),
        { provide: DriveService, useValue: { getDrives: () => throwError(() => new Error('offline')) } },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => false } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(DriveListComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;

    expect(element.querySelector('[role="alert"]')?.textContent).toContain('Drive inventory could not be loaded.');
    expect(element.textContent).not.toContain('No drives match the specified filters.');
  });
});
