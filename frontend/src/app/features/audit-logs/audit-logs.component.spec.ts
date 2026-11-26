import { provideRouter } from '@angular/router';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, Subject, throwError } from 'rxjs';
import { AuditLogPage } from '../../core/models/audit-log.models';
import { AuditLogService } from '../../core/services/audit-log.service';
import { AuditLogsComponent } from './audit-logs.component';

const entry = {
  id: 'e170d5ca-b4c4-4a91-bb6e-d9e43c960001',
  timestamp: '2026-11-25T10:00:00Z',
  username: 'sysadmin',
  action: 'CONFIG_CHANGE' as const,
  resource_type: 'MLModelVersion',
  resource_id: 'model-uuid',
};
const page = (results = [entry], count = results.length): AuditLogPage => ({
  count, next: null, previous: null, results,
});

describe('AuditLogsComponent', () => {
  let fixture: ComponentFixture<AuditLogsComponent>;
  let service: { getAuditLogs: ReturnType<typeof vi.fn> };

  async function setup(response: any = of(page())) {
    service = { getAuditLogs: vi.fn().mockReturnValue(response) };
    await TestBed.configureTestingModule({
      imports: [AuditLogsComponent],
      providers: [provideRouter([]), { provide: AuditLogService, useValue: service }],
    }).compileComponents();
    fixture = TestBed.createComponent(AuditLogsComponent);
    fixture.detectChanges();
  }

  it('loads and displays only the safe audit row fields', async () => {
    await setup();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(service.getAuditLogs).toHaveBeenCalledWith(
      { username: '', action: '', date_from: '', date_to: '' }, 1, 25,
    );
    expect(text).toContain('sysadmin');
    expect(text).toContain('Configuration Changed');
    expect(text).toContain('MLModelVersion');
    expect(text).toContain('model-uuid');
    expect(fixture.nativeElement.querySelector('th')?.textContent).toContain('Timestamp');
  });

  it('applies username, action and date filters from page one', async () => {
    await setup();
    const component = fixture.componentInstance;
    component.currentPage = 3;
    component.filters = {
      username: 'operator', action: 'LOGIN_SUCCESS',
      date_from: '2026-11-01', date_to: '2026-11-25',
    };
    component.applyFilters();
    expect(service.getAuditLogs).toHaveBeenLastCalledWith({
      username: 'operator', action: 'LOGIN_SUCCESS', date_from: '2026-11-01', date_to: '2026-11-25',
    }, 1, 25);
  });

  it('clears filters and returns to the first page', async () => {
    await setup();
    const component = fixture.componentInstance;
    component.currentPage = 2;
    component.filters.username = 'operator';
    component.clearFilters();
    expect(component.filters).toEqual({ username: '', action: '', date_from: '', date_to: '' });
    expect(service.getAuditLogs).toHaveBeenLastCalledWith(component.filters, 1, 25);
  });

  it('shows loading, empty and error states with retry', async () => {
    const pending = new Subject<AuditLogPage>();
    await setup(pending);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Loading audit records');
    pending.next(page([], 0));
    pending.complete();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No audit records found');

    service.getAuditLogs.mockReturnValue(throwError(() => new Error('internal details')));
    fixture.componentInstance.loadLogs();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Audit records could not be loaded');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('internal details');
    (fixture.nativeElement.querySelector('.error-state button') as HTMLButtonElement).click();
    expect(service.getAuditLogs).toHaveBeenCalledTimes(3);
  });

  it('uses server pagination while retaining the current filters', async () => {
    const response = page([entry], 50);
    response.next = '/api/audit-logs/?page=2';
    await setup(of(response));
    const component = fixture.componentInstance;
    component.filters.username = 'sysadmin';
    (fixture.nativeElement.querySelector('.pagination button:last-child') as HTMLButtonElement).click();
    expect(service.getAuditLogs).toHaveBeenLastCalledWith({
      username: 'sysadmin', action: '', date_from: '', date_to: '',
    }, 2, 25);
  });
});
