import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Alert, AlertPage } from '../models/alert.models';
import { AlertService } from './alert.service';

describe('AlertService', () => {
  let service: AlertService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(AlertService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('requests the paginated alert collection with only selected filters', () => {
    service.getAlerts({ status: 'OPEN', alert_type: 'ANOMALY', severity: '', resource: '  drive-uuid  ' }, 2, 10).subscribe();
    const request = http.expectOne((item) => item.url.endsWith('/alerts/'));
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('10');
    expect(request.request.params.get('status')).toBe('OPEN');
    expect(request.request.params.get('alert_type')).toBe('ANOMALY');
    expect(request.request.params.get('resource')).toBe('drive-uuid');
    expect(request.request.params.has('severity')).toBe(false);
    request.flush({ count: 0, next: null, previous: null, results: [] });
  });

  it('uses the detail, unread-count, acknowledge and resolve API routes', () => {
    service.getAlert('alert-id').subscribe();
    http.expectOne((request) => request.url.endsWith('/alerts/alert-id/')).flush({});

    service.getUnreadCount().subscribe();
    http.expectOne((request) => request.url.endsWith('/alerts/unread-count/')).flush({ count: 3 });

    service.acknowledge('alert-id').subscribe();
    const acknowledge = http.expectOne((request) => request.url.endsWith('/alerts/alert-id/acknowledge/'));
    expect(acknowledge.request.method).toBe('POST');
    acknowledge.flush({});

    service.resolve('alert-id').subscribe();
    const resolve = http.expectOne((request) => request.url.endsWith('/alerts/alert-id/resolve/'));
    expect(resolve.request.method).toBe('POST');
    resolve.flush({});
  });

  it('preserves the paginated list and nested alert detail response fields', () => {
    const pageResponse: AlertPage = {
      count: 1,
      next: null,
      previous: null,
      results: [{
        id: 'b38a9609-d510-47fc-8a79-a4b245cc2e8a',
        alert_type: 'FAILURE_RISK',
        severity: 'CRITICAL',
        status: 'ACKNOWLEDGED',
        resource: {
          id: '5dd9e43b-c9a4-4abe-9a22-dcb01230280e',
          name: 'Drive one',
          identifier: 'SERIAL-ONE',
          resource_type: 'DISK',
          status: 'HIGH_RISK',
        },
        first_seen_at: '2026-11-20T10:00:00Z',
        last_seen_at: '2026-11-20T11:00:00Z',
        occurrence_count: 3,
        consecutive_clear_count: 1,
        latest_prediction: {
          id: 42,
          model_type: 'FAILURE_PREDICTION',
          score: 0.91,
          risk_level: 'CRITICAL',
          is_anomalous: null,
          window_start: '2026-11-06T00:00:00Z',
          window_end: '2026-11-20T00:00:00Z',
          created_at: '2026-11-20T11:00:00Z',
          model: {
            id: 'a31c13bb-6e16-4f20-8be9-33a4426726a6',
            name: 'Risk GRU',
            version: 'v2',
            model_type: 'FAILURE_PREDICTION',
            architecture: 'GRU',
          },
        },
        acknowledged_by: 'itpro',
        acknowledged_at: '2026-11-20T11:05:00Z',
        resolved_by: null,
        resolved_at: null,
        resolution_source: '',
        created_at: '2026-11-20T10:00:00Z',
        updated_at: '2026-11-20T11:05:00Z',
      }],
    };
    let receivedPage: AlertPage | undefined;
    service.getAlerts({ status: 'ACKNOWLEDGED' }).subscribe((response) => receivedPage = response);
    http.expectOne((request) => request.url.endsWith('/alerts/')).flush(pageResponse);

    expect(receivedPage?.count).toBe(1);
    expect(receivedPage?.next).toBeNull();
    expect(receivedPage?.results[0].resource.identifier).toBe('SERIAL-ONE');
    expect(receivedPage?.results[0].latest_prediction?.model.version).toBe('v2');
    expect(receivedPage?.results[0].acknowledged_by).toBe('itpro');
    expect(receivedPage?.results[0].resolved_at).toBeNull();

    let receivedDetail: Alert | undefined;
    service.getAlert(pageResponse.results[0].id).subscribe((response) => receivedDetail = response);
    http.expectOne((request) => request.url.endsWith(`/alerts/${pageResponse.results[0].id}/`)).flush(pageResponse.results[0]);
    expect(receivedDetail?.latest_prediction?.model.architecture).toBe('GRU');
    expect(receivedDetail?.consecutive_clear_count).toBe(1);
  });

  it('parses the unread-count response', () => {
    let count: number | undefined;
    service.getUnreadCount().subscribe((response) => count = response.count);
    http.expectOne((request) => request.url.endsWith('/alerts/unread-count/')).flush({ count: 4 });
    expect(count).toBe(4);
  });

  it('propagates backend authorization, not-found, conflict and server errors', () => {
    const cases: Array<{
      call: () => void;
      url: string;
      status: number;
      statusText: string;
    }> = [
      { call: () => service.getAlerts().subscribe({ error: (error) => expect(error.status).toBe(403) }), url: '/alerts/', status: 403, statusText: 'Forbidden' },
      { call: () => service.getAlert('missing-id').subscribe({ error: (error) => expect(error.status).toBe(404) }), url: '/alerts/missing-id/', status: 404, statusText: 'Not Found' },
      { call: () => service.acknowledge('alert-id').subscribe({ error: (error) => expect(error.status).toBe(409) }), url: '/alerts/alert-id/acknowledge/', status: 409, statusText: 'Conflict' },
      { call: () => service.resolve('alert-id').subscribe({ error: (error) => expect(error.status).toBe(500) }), url: '/alerts/alert-id/resolve/', status: 500, statusText: 'Server Error' },
    ];

    for (const testCase of cases) {
      testCase.call();
      const request = http.expectOne((item) => item.url.endsWith(testCase.url));
      request.flush({ detail: 'Safe API error' }, { status: testCase.status, statusText: testCase.statusText });
    }
  });

  it('clears the displayed unread count when refreshing fails', () => {
    service.refreshUnreadCount().subscribe();
    http.expectOne((request) => request.url.endsWith('/alerts/unread-count/')).flush({ count: 5 });
    service.refreshUnreadCount().subscribe((count) => expect(count).toBeNull());
    http.expectOne((request) => request.url.endsWith('/alerts/unread-count/')).flush({}, { status: 503, statusText: 'Unavailable' });
    service.unreadCount$.subscribe((count) => expect(count).toBeNull());
  });

  it('invalidates a pending unread-count response when the session count is cleared', () => {
    let displayedCount: number | null | undefined;
    service.refreshUnreadCount().subscribe((count) => displayedCount = count);
    const pendingRequest = http.expectOne((request) => request.url.endsWith('/alerts/unread-count/'));

    service.clearUnreadCount();
    pendingRequest.flush({ count: 17 });

    let sharedCount: number | null | undefined;
    service.unreadCount$.subscribe((count) => sharedCount = count);
    expect(displayedCount).toBeNull();
    expect(sharedCount).toBeNull();
  });
});
