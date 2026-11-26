import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { DriveService } from './drive.service';

describe('DriveService timeline', () => {
  let service: DriveService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(DriveService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('calls the drive timeline endpoint with supported filters and pagination', () => {
    service.getTimeline('drive-uuid', {
      page: 2,
      page_size: 20,
      type: 'ALERT_RESOLVED',
      from: '2026-11-01',
      to: '2026-11-24',
    }).subscribe();

    const request = http.expectOne((item) => item.url === '/api/drives/drive-uuid/timeline/');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('20');
    expect(request.request.params.get('type')).toBe('ALERT_RESOLVED');
    expect(request.request.params.get('from')).toBe('2026-11-01');
    expect(request.request.params.get('to')).toBe('2026-11-24');
    request.flush({ count: 0, next: null, previous: null, results: [] });
  });
});
