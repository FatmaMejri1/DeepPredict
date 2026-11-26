import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AuditLogService } from './audit-log.service';

describe('AuditLogService', () => {
  let service: AuditLogService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(AuditLogService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('requests the read-only paginated endpoint with selected filters', () => {
    service.getAuditLogs({ username: '  admin ', action: 'CONFIG_CHANGE', date_from: '2026-11-01', date_to: '2026-11-25' }, 2, 10).subscribe();
    const request = http.expectOne((req) => req.url === '/api/audit-logs/');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('username')).toBe('admin');
    expect(request.request.params.get('action')).toBe('CONFIG_CHANGE');
    expect(request.request.params.get('date_from')).toBe('2026-11-01');
    expect(request.request.params.get('date_to')).toBe('2026-11-25');
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('10');
    request.flush({ count: 0, next: null, previous: null, results: [] });
  });

  it('omits empty filters and returns the paginated response', () => {
    let result: any;
    service.getAuditLogs().subscribe((page) => result = page);
    const request = http.expectOne('/api/audit-logs/?page=1&page_size=25');
    request.flush({ count: 1, next: null, previous: null, results: [{
      id: 'e170d5ca-b4c4-4a91-bb6e-d9e43c960001', timestamp: '2026-11-25T10:00:00Z',
      username: 'sysadmin', action: 'CREATE', resource_type: 'Resource', resource_id: 'drive-1',
    }] });
    expect(result.count).toBe(1);
    expect(result.results[0].username).toBe('sysadmin');
  });
});
