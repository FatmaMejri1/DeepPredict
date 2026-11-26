import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';
import { Alert } from '../../../core/models/alert.models';
import { AlertService } from '../../../core/services/alert.service';
import { AuthService } from '../../../core/services/auth.service';
import { AlertDetailComponent } from './alert-detail.component';

const alert: Alert = {
  id: 'alert-1', alert_type: 'FAILURE_RISK', severity: 'HIGH', status: 'OPEN',
  resource: { id: 'drive-1', name: 'Drive One', identifier: 'SERIAL-1', resource_type: 'DISK', status: 'HIGH_RISK' },
  first_seen_at: '2026-01-01T00:00:00Z', last_seen_at: '2026-01-02T00:00:00Z', occurrence_count: 2,
  consecutive_clear_count: 0, latest_prediction: null, acknowledged_by: null, acknowledged_at: null,
  resolved_by: null, resolved_at: null, resolution_source: '', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-02T00:00:00Z',
};

const alertWithPrediction: Alert = {
  ...alert,
  latest_prediction: {
    id: 17,
    model_type: 'FAILURE_PREDICTION',
    score: 0.82,
    risk_level: 'HIGH',
    is_anomalous: null,
    window_start: '2026-01-01T00:00:00Z',
    window_end: '2026-01-14T00:00:00Z',
    created_at: '2026-01-14T00:00:00Z',
    model: {
      id: 'model-1', name: 'Drive Risk GRU', version: 'gru-v2',
      model_type: 'FAILURE_PREDICTION', architecture: 'GRU',
    },
  },
  acknowledged_by: 'itpro-user',
  acknowledged_at: '2026-01-15T00:00:00Z',
};

describe('AlertDetailComponent', () => {
  async function render(options: {
    role?: 'SYSADMIN' | 'IT_PRO' | 'OPERATOR';
    getAlert?: ReturnType<typeof vi.fn>;
    acknowledge?: ReturnType<typeof vi.fn>;
    resolve?: ReturnType<typeof vi.fn>;
    refreshUnreadCount?: ReturnType<typeof vi.fn>;
  } = {}) {
    const getAlert = options.getAlert ?? vi.fn().mockReturnValue(of(alert));
    const acknowledge = options.acknowledge ?? vi.fn().mockReturnValue(of({ ...alert, status: 'ACKNOWLEDGED' }));
    const resolve = options.resolve ?? vi.fn().mockReturnValue(of({ ...alert, status: 'RESOLVED', resolution_source: 'USER' }));
    const refreshUnreadCount = options.refreshUnreadCount ?? vi.fn().mockReturnValue(of(0));
    await TestBed.configureTestingModule({
      imports: [AlertDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: 'alert-1' })) } },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => (options.role ?? 'IT_PRO') !== 'OPERATOR' } },
        { provide: AlertService, useValue: { getAlert, acknowledge, resolve, refreshUnreadCount } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(AlertDetailComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return { fixture, getAlert, acknowledge, resolve, refreshUnreadCount };
  }

  it('renders alert, resource, prediction-unavailable and lifecycle details without telemetry', async () => {
    const { fixture } = await render();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Failure risk alert');
    expect(text).toContain('Drive One');
    expect(text).toContain('SERIAL-1');
    expect(text).toContain('Latest prediction context');
    expect(text).toContain('The linked prediction is no longer available.');
    expect(text).not.toContain('smart_5_raw');
    expect((fixture.nativeElement.querySelector('.resource-name + .resource-identifier + p + a') as HTMLAnchorElement).getAttribute('href')).toBe('/drives/drive-1');
    fixture.destroy();
  });

  it('renders populated prediction, model and acknowledgement metadata', async () => {
    const { fixture } = await render({ getAlert: vi.fn().mockReturnValue(of(alertWithPrediction)) });
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('FAILURE_PREDICTION');
    expect(text).toContain('0.82');
    expect(text).toContain('Drive Risk GRU');
    expect(text).toContain('gru-v2');
    expect(text).toContain('GRU');
    expect(text).toContain('itpro-user');
    expect(text).not.toContain('smart_5_raw');
    fixture.destroy();
  });

  it('shows acknowledge/resolve to IT_PRO and refreshes the detail and unread count', async () => {
    const updated = { ...alert, status: 'ACKNOWLEDGED' as const };
    const acknowledge = vi.fn().mockReturnValue(of(updated));
    const getAlert = vi.fn().mockReturnValue(of(alert));
    const refreshUnreadCount = vi.fn().mockReturnValue(of(0));
    const { fixture } = await render({ role: 'IT_PRO', acknowledge, getAlert, refreshUnreadCount });
    (fixture.nativeElement.querySelector('button') as HTMLButtonElement).click();
    await fixture.whenStable(); fixture.detectChanges();
    expect(acknowledge).toHaveBeenCalledWith('alert-1');
    expect(fixture.componentInstance.alert?.status).toBe('ACKNOWLEDGED');
    expect(refreshUnreadCount).toHaveBeenCalledTimes(1);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Resolve alert');
    fixture.destroy();
  });

  it('manually resolves an alert and refreshes the unread count', async () => {
    const resolved = { ...alert, status: 'RESOLVED' as const, resolution_source: 'USER' as const };
    const resolve = vi.fn().mockReturnValue(of(resolved));
    const refreshUnreadCount = vi.fn().mockReturnValue(of(0));
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { fixture } = await render({ resolve, refreshUnreadCount });
    const resolveButton = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')]
      .find((button) => button.textContent?.includes('Resolve alert')) as HTMLButtonElement;
    resolveButton.click();
    await fixture.whenStable(); fixture.detectChanges();
    expect(resolve).toHaveBeenCalledWith('alert-1');
    expect(confirm).toHaveBeenCalledWith('Resolve the active alert for SERIAL-1?');
    expect(fixture.componentInstance.alert?.status).toBe('RESOLVED');
    expect(fixture.componentInstance.alert?.resolution_source).toBe('USER');
    expect(refreshUnreadCount).toHaveBeenCalledTimes(1);
    fixture.destroy();
    confirm.mockRestore();
  });

  it('does not submit manual resolution when confirmation is cancelled', async () => {
    const resolve = vi.fn().mockReturnValue(of({ ...alert, status: 'RESOLVED' as const }));
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const { fixture } = await render({ resolve });
    const resolveButton = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')]
      .find((button) => button.textContent?.includes('Resolve alert')) as HTMLButtonElement;
    resolveButton.click();

    expect(confirm).toHaveBeenCalledTimes(1);
    expect(resolve).not.toHaveBeenCalled();
    expect(fixture.componentInstance.alert?.status).toBe('OPEN');
    fixture.destroy();
    confirm.mockRestore();
  });

  it('hides write controls from OPERATOR', async () => {
    const { fixture } = await render({ role: 'OPERATOR' });
    expect((fixture.nativeElement as HTMLElement).querySelector('.actions')).toBeNull();
    fixture.destroy();
  });

  it('shows only valid actions to SYSADMIN for an open alert', async () => {
    const { fixture } = await render({ role: 'SYSADMIN' });
    const buttons = [...(fixture.nativeElement as HTMLElement).querySelectorAll('.actions button')]
      .map((button) => button.textContent?.trim());
    expect(buttons).toEqual(['Acknowledge', 'Resolve alert']);
    fixture.destroy();
  });

  it('prevents duplicate submissions while an action is pending', async () => {
    const response = new Subject<Alert>();
    const acknowledge = vi.fn().mockReturnValue(response);
    const { fixture } = await render({ acknowledge });
    fixture.componentInstance.acknowledge();
    fixture.componentInstance.acknowledge();
    expect(acknowledge).toHaveBeenCalledTimes(1);
    expect(fixture.componentInstance.actionInProgress).toBe('acknowledge');
    response.next({ ...alert, status: 'ACKNOWLEDGED' });
    response.complete();
    await fixture.whenStable(); fixture.detectChanges();
    expect(fixture.componentInstance.actionInProgress).toBeNull();
    fixture.destroy();
  });

  it('reports a lifecycle conflict safely and reloads the current alert', async () => {
    const getAlert = vi.fn().mockReturnValue(of(alert));
    const acknowledge = vi.fn().mockReturnValue(throwError(() => ({ status: 409 })));
    const { fixture } = await render({ getAlert, acknowledge });
    (fixture.nativeElement.querySelector('.actions button') as HTMLButtonElement).click();
    await fixture.whenStable(); fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('This alert changed state before the action completed.');
    expect(getAlert).toHaveBeenCalledTimes(2);
    fixture.destroy();
  });

  it('shows a safe forbidden-action message and reloads current state', async () => {
    const getAlert = vi.fn().mockReturnValue(of(alert));
    const acknowledge = vi.fn().mockReturnValue(throwError(() => ({ status: 403, error: 'private detail' })));
    const { fixture } = await render({ getAlert, acknowledge });
    fixture.componentInstance.acknowledge();
    await fixture.whenStable(); fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Your role cannot change this alert.');
    expect(text).not.toContain('private detail');
    expect(getAlert).toHaveBeenCalledTimes(2);
    expect(fixture.componentInstance.alert?.status).toBe('OPEN');
    fixture.destroy();
  });

  it('ignores a pending action response after the route changes to another alert', async () => {
    const routeParams = new Subject<ReturnType<typeof convertToParamMap>>();
    const pendingAction = new Subject<Alert>();
    const firstAlert = alert;
    const secondAlert: Alert = {
      ...alert,
      id: 'alert-2',
      status: 'ACKNOWLEDGED',
      resource: { ...alert.resource, id: 'drive-2', name: 'Drive Two', identifier: 'SERIAL-2' },
    };
    const getAlert = vi.fn((id: string) => of(id === 'alert-2' ? secondAlert : firstAlert));
    const acknowledge = vi.fn(() => pendingAction.asObservable());
    const refreshUnreadCount = vi.fn().mockReturnValue(of(0));

    await TestBed.configureTestingModule({
      imports: [AlertDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap: routeParams.asObservable() } },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => true } },
        { provide: AlertService, useValue: { getAlert, acknowledge, resolve: vi.fn(), refreshUnreadCount } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(AlertDetailComponent);
    fixture.detectChanges();
    routeParams.next(convertToParamMap({ id: 'alert-1' }));
    await fixture.whenStable(); fixture.detectChanges();
    fixture.componentInstance.acknowledge();
    expect(fixture.componentInstance.actionInProgress).toBe('acknowledge');

    routeParams.next(convertToParamMap({ id: 'alert-2' }));
    await fixture.whenStable(); fixture.detectChanges();
    expect(fixture.componentInstance.alert?.id).toBe('alert-2');
    expect(fixture.componentInstance.actionInProgress).toBeNull();

    pendingAction.next({ ...firstAlert, status: 'ACKNOWLEDGED', acknowledged_by: 'itpro-user' });
    pendingAction.complete();
    fixture.detectChanges();

    expect(fixture.componentInstance.alert?.id).toBe('alert-2');
    expect(fixture.componentInstance.alert?.resource.identifier).toBe('SERIAL-2');
    expect(fixture.componentInstance.actionInProgress).toBeNull();
    expect(fixture.componentInstance.actionError).toBe('');
    expect(refreshUnreadCount).not.toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Drive Two');
    fixture.destroy();
  });

  it('refetches alert state after a failed action and displays the recovered state', async () => {
    const refreshedAlert = { ...alert, status: 'ACKNOWLEDGED' as const, acknowledged_by: 'itpro-user' };
    const getAlert = vi.fn()
      .mockReturnValueOnce(of(alert))
      .mockReturnValueOnce(of(refreshedAlert));
    const acknowledge = vi.fn().mockReturnValue(throwError(() => ({ status: 500 })));
    const refreshUnreadCount = vi.fn().mockReturnValue(of(0));
    const { fixture } = await render({ getAlert, acknowledge, refreshUnreadCount });
    fixture.componentInstance.acknowledge();
    await fixture.whenStable(); fixture.detectChanges();
    expect(getAlert).toHaveBeenCalledTimes(2);
    expect(fixture.componentInstance.alert?.status).toBe('ACKNOWLEDGED');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('The action response could not be confirmed');
    expect(refreshUnreadCount).toHaveBeenCalledTimes(1);
    fixture.destroy();
  });

  it('clears potentially stale alert data if recovery also fails', async () => {
    const getAlert = vi.fn()
      .mockReturnValueOnce(of(alert))
      .mockReturnValueOnce(throwError(() => new Error('offline')));
    const acknowledge = vi.fn().mockReturnValue(throwError(() => ({ status: 500 })));
    const { fixture } = await render({ getAlert, acknowledge });
    fixture.componentInstance.acknowledge();
    await fixture.whenStable(); fixture.detectChanges();
    expect(fixture.componentInstance.alert).toBeNull();
    expect(fixture.componentInstance.actionInProgress).toBeNull();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('The alert state could not be refreshed');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('Drive One');
    fixture.destroy();
  });

  it('keeps loading and retry states for an unavailable detail request', async () => {
    const response = new Subject<Alert>();
    const getAlert = vi.fn().mockReturnValue(response);
    const rendered = await render({ getAlert });
    expect((rendered.fixture.nativeElement as HTMLElement).querySelector('[role="status"]')?.textContent).toContain('Loading alert');
    response.error(new Error('offline'));
    await rendered.fixture.whenStable(); rendered.fixture.detectChanges();
    expect((rendered.fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')?.textContent).toContain('Alert details could not be loaded');

    getAlert.mockReturnValueOnce(of(alert));
    (rendered.fixture.nativeElement.querySelector('[role="alert"] button') as HTMLButtonElement).click();
    await rendered.fixture.whenStable(); rendered.fixture.detectChanges();
    expect(rendered.fixture.componentInstance.alert?.id).toBe('alert-1');
    rendered.fixture.destroy();
  });

  it('does not expose backend details when a lifecycle action fails', async () => {
    const acknowledge = vi.fn().mockReturnValue(throwError(() => ({ status: 500, error: 'private database detail' })));
    const { fixture } = await render({ acknowledge });
    (fixture.nativeElement.querySelector('.actions button') as HTMLButtonElement).click();
    await fixture.whenStable(); fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('The action response could not be confirmed. The latest alert state is being checked.');
    expect(text).not.toContain('private database detail');
    fixture.destroy();
  });
});
