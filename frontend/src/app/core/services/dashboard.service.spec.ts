import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { DashboardService } from './dashboard.service';

describe('DashboardService filters', () => {
  let service: DashboardService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(DashboardService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('sends supported filters to the existing summary and activity endpoints', () => {
    const filters = { status: 'WARNING', risk_level: 'MEDIUM', is_anomalous: 'true' };
    service.getSummary(filters).subscribe();
    service.getRecentActivity(filters).subscribe();

    const summaryRequest = http.expectOne((request) => request.url.endsWith('/dashboard/summary/'));
    const activityRequest = http.expectOne((request) => request.url.endsWith('/dashboard/activity/'));
    for (const request of [summaryRequest, activityRequest]) {
      expect(request.request.method).toBe('GET');
      expect(request.request.params.get('status')).toBe('WARNING');
      expect(request.request.params.get('risk_level')).toBe('MEDIUM');
      expect(request.request.params.get('is_anomalous')).toBe('true');
      request.flush({});
    }
  });

  it('does not add empty filter parameters to unfiltered requests', () => {
    service.getSummary({ status: '', risk_level: '', is_anomalous: '' }).subscribe();

    const request = http.expectOne((item) => item.url.endsWith('/dashboard/summary/'));
    expect(request.request.params.keys()).toEqual([]);
    request.flush({});
  });
});
