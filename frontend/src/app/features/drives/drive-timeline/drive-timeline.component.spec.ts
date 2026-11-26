import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';
import { DriveTimelineEvent, DriveTimelinePage } from '../../../core/models/drive.models';
import { DriveService } from '../../../core/services/drive.service';
import { DriveTimelineComponent } from './drive-timeline.component';

const resource = { id: 'drive-uuid', name: 'Drive One', identifier: 'SERIAL-ONE' };
const event = (id: string, event_type: DriveTimelineEvent['event_type'], occurred_at: string, data: DriveTimelineEvent['data'], actor: string | null = null): DriveTimelineEvent => ({
  id,
  event_type,
  occurred_at,
  resource,
  actor,
  data,
});
const emptyPage = (count = 0): DriveTimelinePage => ({ count, next: null, previous: null, results: [] });
const allEvents: DriveTimelineEvent[] = [
  event('resource_audit:1', 'RESOURCE_AUDIT', '2026-11-20T10:06:00Z', {
    action: 'UPDATE', description: 'Resource updated', details: { secret: 'not for display' },
  } as DriveTimelineEvent['data'], 'admin'),
  event('alert_resolved:2', 'ALERT_RESOLVED', '2026-11-20T10:05:30Z', {
    alert_id: 'alert-2', alert_type: 'ANOMALY', severity: 'HIGH', resolution_source: 'USER',
  }, 'sysadmin'),
  event('alert_resolved:1', 'ALERT_RESOLVED', '2026-11-20T10:05:00Z', {
    alert_id: 'alert-1', alert_type: 'FAILURE_RISK', severity: 'CRITICAL', resolution_source: 'AUTO',
  }),
  event('alert_acknowledged:1', 'ALERT_ACKNOWLEDGED', '2026-11-20T10:04:00Z', {
    alert_id: 'alert-1', alert_type: 'FAILURE_RISK', severity: 'CRITICAL',
  }, 'itpro'),
  event('alert_opened:1', 'ALERT_OPENED', '2026-11-20T10:03:00Z', {
    alert_id: 'alert-1', alert_type: 'FAILURE_RISK', severity: 'CRITICAL',
  }),
  event('prediction:2', 'PREDICTION', '2026-11-20T10:02:00Z', {
    prediction_type: 'ANOMALY_DETECTION', score: 1.4, risk_level: null, is_anomalous: true,
    horizon_days: null, window_start: '2026-11-06T10:00:00Z', window_end: '2026-11-20T10:00:00Z',
    model: { name: 'LSTM AE', version: 'v1', model_type: 'ANOMALY_DETECTION', architecture: 'LSTM_AUTOENCODER' },
  }),
  event('prediction:1', 'PREDICTION', '2026-11-20T10:01:00Z', {
    prediction_type: 'FAILURE_PREDICTION', score: 0.82, risk_level: 'HIGH', is_anomalous: null,
    horizon_days: 7, window_start: '2026-11-06T10:00:00Z', window_end: '2026-11-20T10:00:00Z',
    model: { name: 'GRU risk', version: 'v2', model_type: 'FAILURE_PREDICTION', architecture: 'GRU' },
  }),
  event('telemetry_reading:1', 'TELEMETRY_READING', '2026-11-20T10:00:00Z', { source: 'Backblaze' }),
];

describe('DriveTimelineComponent', () => {
  async function render(getTimeline: ReturnType<typeof vi.fn>) {
    await TestBed.configureTestingModule({
      imports: [DriveTimelineComponent],
      providers: [provideRouter([]), { provide: DriveService, useValue: { getTimeline } }],
    }).compileComponents();
    const fixture = TestBed.createComponent(DriveTimelineComponent);
    fixture.componentRef.setInput('driveId', resource.id);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return fixture;
  }

  it('renders every backend event kind once in chronological order with only supplied safe metadata', async () => {
    const fixture = await render(vi.fn().mockReturnValue(of({ count: allEvents.length, next: null, previous: null, results: allEvents })));
    const element = fixture.nativeElement as HTMLElement;
    const rows = Array.from(element.querySelectorAll('.timeline-event'));
    expect(rows).toHaveLength(8);
    expect(rows.map((row) => row.querySelector('h3')?.textContent?.trim())).toEqual([
      'Resource updated', 'Alert resolved', 'Alert resolved', 'Alert acknowledged', 'Alert opened',
      'Anomaly prediction', 'Failure-risk prediction', 'SMART telemetry reading',
    ]);
    expect(element.textContent).toContain('Source: Backblaze');
    expect(element.textContent).toContain('HIGH');
    expect(element.textContent).toContain('0.820');
    expect(element.textContent).toContain('GRU risk v2 (GRU)');
    expect(element.textContent).toContain('Anomaly: Detected');
    expect(element.textContent).toContain('LSTM AE v1 (LSTM_AUTOENCODER)');
    expect(element.querySelector('time[datetime="2026-11-06T10:00:00Z"]')).not.toBeNull();
    expect(element.querySelector('time[datetime="2026-11-20T10:00:00Z"]')).not.toBeNull();
    expect(element.textContent).toContain('Actor: itpro');
    expect(element.textContent).toContain('Actor: sysadmin');
    expect(element.textContent).toContain('Resolution: Automatic');
    expect(element.textContent).toContain('Resolution: Manual');
    expect(element.textContent).toContain('Action: UPDATE');
    expect(element.querySelectorAll('a[href="/alerts/alert-1"]')).toHaveLength(3);
    expect(element.querySelectorAll('a[href="/alerts/alert-2"]')).toHaveLength(1);
    expect(element.textContent).not.toContain('Actor: null');
    expect(rows[5].textContent).not.toContain('Actor:');
    expect(rows[6].textContent).not.toContain('Actor:');
    expect(element.textContent).not.toContain('not for display');
    expect(element.textContent).not.toContain('values');
    expect(element.querySelector('.history-table')).toBeNull();
    fixture.destroy();
  });

  it('shows initial loading, empty and empty-filtered states distinctly', async () => {
    const pending = new Subject<DriveTimelinePage>();
    const fixture = await render(vi.fn().mockReturnValueOnce(pending).mockReturnValue(of(emptyPage())));
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="status"]')?.textContent).toContain('Loading timeline');
    pending.next(emptyPage());
    pending.complete();
    await fixture.whenStable(); fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No timeline events are available');

    fixture.componentInstance.selectedType = 'PREDICTION';
    fixture.componentInstance.filtersChanged();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No events match the selected filters');
    fixture.destroy();
  });

  it('shows a safe error and retries the same query', async () => {
    const getTimeline = vi.fn().mockReturnValueOnce(throwError(() => new Error('database detail'))).mockReturnValueOnce(of(emptyPage()));
    const fixture = await render(getTimeline);
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('[role="alert"]')?.textContent).toContain('The drive timeline could not be loaded.');
    expect(element.textContent).not.toContain('database detail');
    fixture.componentInstance.selectedType = 'ALERT_RESOLVED';
    fixture.componentInstance.fromDate = '2026-11-01';
    fixture.detectChanges();
    (element.querySelector('[role="alert"] button') as HTMLButtonElement).click();
    await fixture.whenStable(); fixture.detectChanges();
    expect(getTimeline).toHaveBeenLastCalledWith(resource.id, {
      page: 1, page_size: 20, type: 'ALERT_RESOLVED', from: '2026-11-01', to: undefined,
    });
    expect(element.querySelector('[role="alert"]')).toBeNull();
    fixture.destroy();
  });

  it('validates an inverted date range locally instead of showing an API outage', async () => {
    const getTimeline = vi.fn().mockReturnValue(of(emptyPage()));
    const fixture = await render(getTimeline);
    fixture.componentInstance.fromDate = '2026-11-24';
    fixture.componentInstance.toDate = '2026-11-01';
    fixture.componentInstance.filtersChanged();
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('[role="alert"]')?.textContent).toContain('From date must be on or before To date.');
    expect(element.querySelector('[role="alert"] button')).toBeNull();
    expect(element.textContent).not.toContain('No events match');
    expect(getTimeline).toHaveBeenCalledTimes(1);

    fixture.componentInstance.toDate = '2026-11-30';
    fixture.componentInstance.filtersChanged();
    fixture.detectChanges();
    expect(getTimeline).toHaveBeenCalledTimes(2);
    expect(element.querySelector('[role="alert"]')).toBeNull();
    fixture.destroy();
  });

  it('sends selected type/date filters, resets page, clears filters, and preserves filters on page navigation', async () => {
    const getTimeline = vi.fn((_id: string, query: { page: number }) => of({
      count: 45,
      next: query.page < 3 ? `/api/drives/x/timeline/?page=${query.page + 1}` : null,
      previous: query.page > 1 ? `/api/drives/x/timeline/?page=${query.page - 1}` : null,
      results: allEvents.slice(0, 1),
    }));
    const fixture = await render(getTimeline);
    const element = fixture.nativeElement as HTMLElement;
    const select = element.querySelector<HTMLSelectElement>('.timeline-filters select')!;
    select.value = 'PREDICTION';
    select.dispatchEvent(new Event('change'));
    const dates = element.querySelectorAll<HTMLInputElement>('.timeline-filters input');
    dates[0].value = '2026-11-01';
    dates[0].dispatchEvent(new Event('input'));
    dates[1].value = '2026-11-24';
    dates[1].dispatchEvent(new Event('input'));
    expect(getTimeline).toHaveBeenLastCalledWith(resource.id, {
      page: 1, page_size: 20, type: 'PREDICTION', from: '2026-11-01', to: '2026-11-24',
    });

    (element.querySelector('.timeline-pagination button:last-child') as HTMLButtonElement).click();
    await fixture.whenStable(); fixture.detectChanges();
    expect(getTimeline).toHaveBeenLastCalledWith(resource.id, {
      page: 2, page_size: 20, type: 'PREDICTION', from: '2026-11-01', to: '2026-11-24',
    });
    expect(element.textContent).toContain('Page 2 of 3');

    (element.querySelector('.timeline-pagination button:first-child') as HTMLButtonElement).click();
    await fixture.whenStable(); fixture.detectChanges();
    expect(getTimeline).toHaveBeenLastCalledWith(resource.id, {
      page: 1, page_size: 20, type: 'PREDICTION', from: '2026-11-01', to: '2026-11-24',
    });

    select.value = 'ALERT_OPENED';
    select.dispatchEvent(new Event('change'));
    expect(getTimeline).toHaveBeenLastCalledWith(resource.id, {
      page: 1, page_size: 20, type: 'ALERT_OPENED', from: '2026-11-01', to: '2026-11-24',
    });
    (element.querySelector('.timeline-heading button') as HTMLButtonElement).click();
    expect(getTimeline).toHaveBeenLastCalledWith(resource.id, {
      page: 1, page_size: 20, type: '', from: undefined, to: undefined,
    });
    fixture.destroy();
  });

  it('shows pagination loading state and ignores obsolete responses after a newer request', async () => {
    const older = new Subject<DriveTimelinePage>();
    const latest = new Subject<DriveTimelinePage>();
    const getTimeline = vi.fn().mockReturnValueOnce(older).mockReturnValueOnce(latest);
    const fixture = await render(getTimeline);
    fixture.componentInstance.selectedType = 'PREDICTION';
    fixture.componentInstance.filtersChanged();
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="status"]')?.textContent).toContain('Loading timeline');
    latest.next({ count: 1, next: null, previous: null, results: [allEvents[6]] });
    latest.complete();
    older.next({ count: 1, next: null, previous: null, results: [allEvents[0]] });
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Failure-risk prediction');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('SMART telemetry reading');
    fixture.destroy();
  });

  it('loads the new drive once on input change and still reloads on refresh-token changes', async () => {
    const getTimeline = vi.fn().mockReturnValue(of({
      count: 60, next: '/next', previous: '/previous', results: [],
    }));
    const fixture = await render(getTimeline);
    const component = fixture.componentInstance;
    component.page = 3;
    component.selectedType = 'ALERT_RESOLVED';
    component.fromDate = '2026-11-01';

    fixture.componentRef.setInput('driveId', 'drive-two');
    fixture.componentRef.setInput('refreshToken', 1);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(getTimeline).toHaveBeenCalledTimes(2);
    expect(getTimeline).toHaveBeenLastCalledWith('drive-two', {
      page: 1, page_size: 20, type: 'ALERT_RESOLVED', from: '2026-11-01', to: undefined,
    });
    expect(component.page).toBe(1);

    fixture.componentRef.setInput('refreshToken', 2);
    fixture.detectChanges();
    await fixture.whenStable();
    expect(getTimeline).toHaveBeenCalledTimes(3);
    expect(getTimeline).toHaveBeenLastCalledWith('drive-two', {
      page: 1, page_size: 20, type: 'ALERT_RESOLVED', from: '2026-11-01', to: undefined,
    });
    fixture.destroy();
  });
});
