import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject, NEVER, Observable, Subject, of, throwError } from 'rxjs';
import { DriveDetail, DrivePredictionHistoryItem, DriveTelemetryData, DriveTimelinePage } from '../../../core/models/drive.models';
import { PredictionRunResponse } from '../../../core/models/prediction.models';
import { AuthService } from '../../../core/services/auth.service';
import { DriveService } from '../../../core/services/drive.service';
import { PredictionService } from '../../../core/services/prediction.service';
import { DriveDetailComponent } from './drive-detail.component';

const emptyTimeline: DriveTimelinePage = { count: 0, next: null, previous: null, results: [] };

describe('DriveDetailComponent', () => {
  it('shows an explicit unscored state when no predictions exist', async () => {
    const drive: DriveDetail = {
      id: '00000000-0000-0000-0000-000000000456',
      name: 'Unscored drive',
      identifier: 'UNSCORED-456',
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
      attributes: {},
      created_at: '2026-11-20T00:00:00Z',
      updated_at: '2026-11-20T00:00:00Z',
    };
    await TestBed.configureTestingModule({
      imports: [DriveDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: drive.id })) } },
        { provide: DriveService, useValue: { getDrive: () => of(drive), getTelemetry: () => NEVER, getPredictionHistory: () => of([]), getTimeline: () => of(emptyTimeline) } },
        { provide: PredictionService, useValue: { runPrediction: () => NEVER } },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => false } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(DriveDetailComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;

    expect(element.querySelector('.drive-title')?.textContent).toContain('UNSCORED-456');
    expect(element.textContent).toContain('NOT SCORED');
    expect(element.textContent).toContain('Not yet scored');
    expect(element.textContent).toContain('NOT EVALUATED');
    expect(element.textContent).toContain('No score available');
    expect(element.textContent).toContain('No timeline events are available for this drive.');
    expect(element.querySelector('.history-table')).toBeNull();
    expect(fixture.componentInstance.formatCapacity(undefined)).toBe('—');
  });

  it('keeps the SMART and risk chart views available alongside the timeline', async () => {
    const drive: DriveDetail = {
      id: '00000000-0000-0000-0000-000000000456', name: 'Chart drive', identifier: 'CHART-456',
      model: '', vendor: '', datacenter: '', status: 'HEALTHY', risk_level: null, risk_score: null,
      scored_until: null, is_anomalous: false, anomaly_evaluated: false, last_reading: null,
      attributes: {}, created_at: '', updated_at: '',
    };
    await TestBed.configureTestingModule({
      imports: [DriveDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: drive.id })) } },
        {
          provide: DriveService,
          useValue: {
            getDrive: () => of(drive), getTelemetry: () => NEVER, getPredictionHistory: () => of([]),
            getTimeline: () => of(emptyTimeline),
          },
        },
        { provide: PredictionService, useValue: { runPrediction: () => NEVER } },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => false } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(DriveDetailComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.componentInstance.telemetryLoading = false;
    fixture.componentInstance.telemetryData = {
      smart: { labels: ['2026-11-20'], series: [{ label: 'SMART 5', values: [2] }] },
      risk: { labels: ['2026-11-20'], scores: [0.4] },
      thresholds: { medium: 0.3 },
    };
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelectorAll('.charts-grid canvas')).toHaveLength(2);
    expect(element.querySelector('[aria-label="SMART telemetry history range"]')).not.toBeNull();
    expect(element.querySelector('app-drive-timeline')).not.toBeNull();
    fixture.destroy();
  });

  it('replaces the prediction history table with the unified prediction timeline', async () => {
    const drive: DriveDetail = {
      id: '00000000-0000-0000-0000-000000000789',
      name: 'Drive with history',
      identifier: 'HISTORY-789',
      model: 'Model',
      vendor: 'Vendor',
      datacenter: 'DC',
      status: 'HIGH_RISK',
      risk_level: 'HIGH',
      risk_score: 0.82,
      scored_until: '2026-11-19T10:00:00Z',
      is_anomalous: true,
      anomaly_evaluated: true,
      last_reading: null,
      attributes: {},
      created_at: '2026-11-01T00:00:00Z',
      updated_at: '2026-11-19T10:00:00Z',
    };
    const prediction: DrivePredictionHistoryItem = {
      id: 42,
      prediction_type: 'FAILURE_PREDICTION',
      score: 0.82,
      risk_level: 'HIGH',
      is_anomalous: null,
      horizon_days: 7,
      window_start: '2026-11-05T00:00:00Z',
      window_end: '2026-11-19T10:00:00Z',
      created_at: '2026-11-19T10:01:00Z',
      model: { name: 'Risk GRU', version: 'v2', model_type: 'FAILURE_PREDICTION', architecture: 'GRU' },
    };
    await TestBed.configureTestingModule({
      imports: [DriveDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: drive.id })) } },
        {
          provide: DriveService,
          useValue: {
            getDrive: () => of(drive), getTelemetry: () => NEVER, getPredictionHistory: () => of([prediction]),
            getTimeline: () => of({
              count: 1, next: null, previous: null,
              results: [{
                id: 'prediction:42', event_type: 'PREDICTION', occurred_at: prediction.created_at,
                resource: { id: drive.id, name: drive.name, identifier: drive.identifier }, actor: null,
                data: {
                  prediction_type: prediction.prediction_type, score: prediction.score,
                  risk_level: prediction.risk_level, is_anomalous: prediction.is_anomalous,
                  horizon_days: prediction.horizon_days, window_start: prediction.window_start,
                  window_end: prediction.window_end, model: prediction.model,
                },
              }],
            }),
          },
        },
        { provide: PredictionService, useValue: { runPrediction: () => NEVER } },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => false } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(DriveDetailComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const timeline = fixture.nativeElement.querySelector('.timeline-list') as HTMLOListElement;

    expect(timeline.textContent).toContain('Failure-risk prediction');
    expect(timeline.textContent).toContain('HIGH');
    expect(timeline.textContent).toContain('0.820');
    expect(timeline.textContent).toContain('Risk GRU');
    expect(timeline.textContent).toContain('v2');
    expect(timeline.textContent).toContain('Nov 19, 2026');
    expect(fixture.nativeElement.querySelector('.history-table')).toBeNull();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('UNKNOWN');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('NORMAL PATTERN');
  });

  it('uses the selected history range and reports missing active risk thresholds', async () => {
    const driveId = '00000000-0000-0000-0000-000000000789';
    const requestedRanges: number[] = [];
    await TestBed.configureTestingModule({
      imports: [DriveDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: driveId })) } },
        {
          provide: DriveService,
          useValue: {
            getDrive: () => of({
              id: driveId, name: 'Range drive', identifier: 'RANGE-789', model: '', vendor: '', datacenter: '',
              status: 'HEALTHY', risk_level: null, risk_score: null, scored_until: null, is_anomalous: false,
              anomaly_evaluated: false, last_reading: null, attributes: {}, created_at: '', updated_at: '',
            }),
            getTelemetry: (_id: string, days: number) => { requestedRanges.push(days); return NEVER; },
            getPredictionHistory: () => of([]),
            getTimeline: () => of(emptyTimeline),
          },
        },
        { provide: PredictionService, useValue: { runPrediction: () => NEVER } },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => false } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(DriveDetailComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.componentInstance.changeTelemetryRange(30);

    expect(requestedRanges).toEqual([90, 30]);
    expect(fixture.componentInstance.riskThresholdSummary).toBe('');
    fixture.componentInstance.telemetryData = {
      smart: { labels: [], series: [] },
      risk: { labels: [], scores: [] },
      thresholds: { medium: 0.42, high: 0.67 },
    };
    expect(fixture.componentInstance.riskThresholdSummary).toBe('Medium (0.42), High (0.67)');
  });

  it('cancels obsolete telemetry range requests and keeps only the latest response', async () => {
    const driveId = '00000000-0000-0000-0000-000000000789';
    const requests = new Map<number, Subject<DriveTelemetryData>>();
    await TestBed.configureTestingModule({
      imports: [DriveDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: driveId })) } },
        {
          provide: DriveService,
          useValue: {
            getDrive: () => of({
              id: driveId, name: 'Range drive', identifier: 'RANGE-789', model: '', vendor: '', datacenter: '',
              status: 'HEALTHY', risk_level: null, risk_score: null, scored_until: null, is_anomalous: false,
              anomaly_evaluated: false, last_reading: null, attributes: {}, created_at: '', updated_at: '',
            }),
            getTelemetry: (_id: string, days: number) => {
              const request = new Subject<DriveTelemetryData>();
              requests.set(days, request);
              return request as Observable<DriveTelemetryData>;
            },
            getPredictionHistory: () => of([]),
            getTimeline: () => of(emptyTimeline),
          },
        },
        { provide: PredictionService, useValue: { runPrediction: () => NEVER } },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => false } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(DriveDetailComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    fixture.componentInstance.changeTelemetryRange(30);
    fixture.componentInstance.changeTelemetryRange(180);
    expect(requests.get(90)?.observed).toBe(false);
    expect(requests.get(30)?.observed).toBe(false);
    expect(requests.get(180)?.observed).toBe(true);

    const telemetry = (label: string): DriveTelemetryData => ({
      smart: { labels: [label], series: [] },
      risk: { labels: [], scores: [] },
      thresholds: {},
    });
    requests.get(180)?.next(telemetry('latest-range'));
    requests.get(180)?.complete();
    requests.get(30)?.next(telemetry('obsolete-range'));
    requests.get(90)?.next(telemetry('initial-range'));
    fixture.detectChanges();

    expect(fixture.componentInstance.telemetryDays).toBe(180);
    expect(fixture.componentInstance.telemetryData?.smart.labels).toEqual(['latest-range']);
    expect(fixture.componentInstance.telemetryLoading).toBe(false);
    expect(fixture.componentInstance.telemetryError).toBe('');
    fixture.destroy();
  });

  it('clears stale anomaly assessment after a failed history reload and retries successfully', async () => {
    const driveId = '00000000-0000-0000-0000-000000000789';
    const historyRequests: Subject<DrivePredictionHistoryItem[]>[] = [];
    const prediction: DrivePredictionHistoryItem = {
      id: 42,
      prediction_type: 'ANOMALY_DETECTION',
      score: 0.82,
      risk_level: null,
      is_anomalous: true,
      horizon_days: null,
      window_start: '2026-11-05T00:00:00Z',
      window_end: '2026-11-19T10:00:00Z',
      created_at: '2026-11-19T10:01:00Z',
      model: { name: 'LSTM AE', version: 'v2', model_type: 'ANOMALY_DETECTION', architecture: 'LSTM_AUTOENCODER' },
    };
    await TestBed.configureTestingModule({
      imports: [DriveDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: driveId })) } },
        {
          provide: DriveService,
          useValue: {
            getDrive: () => of({
              id: driveId, name: 'History drive', identifier: 'HISTORY-789', model: '', vendor: '', datacenter: '',
              status: 'HEALTHY', risk_level: null, risk_score: null, scored_until: null, is_anomalous: false,
              anomaly_evaluated: false, last_reading: null, attributes: {}, created_at: '', updated_at: '',
            }),
            getTelemetry: () => NEVER,
            getPredictionHistory: () => {
              const request = new Subject<DrivePredictionHistoryItem[]>();
              historyRequests.push(request);
              return request;
            },
            getTimeline: () => of(emptyTimeline),
          },
        },
        { provide: PredictionService, useValue: { runPrediction: () => NEVER } },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => false } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(DriveDetailComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    historyRequests[0].next([prediction]);
    historyRequests[0].complete();
    fixture.detectChanges();
    expect(fixture.componentInstance.anomalyScore).toBe(0.82);
    expect(fixture.componentInstance.anomalyStatus).toBe('ANOMALOUS');

    fixture.componentInstance.loadHistory();
    expect(fixture.componentInstance.predictionHistory).toEqual([]);
    historyRequests[1].error(new Error('temporary history failure'));
    fixture.detectChanges();
    const failedHistory = fixture.nativeElement as HTMLElement;
    expect(fixture.componentInstance.anomalyScore).toBeNull();
    expect(fixture.componentInstance.anomalyStatus).toBe('UNKNOWN');
    expect(failedHistory.textContent).toContain('Assessment unavailable');
    expect(failedHistory.textContent).not.toContain('0.820');

    failedHistory.querySelector<HTMLButtonElement>('.assessment-card button')?.click();
    expect(historyRequests).toHaveLength(3);
    historyRequests[2].next([prediction]);
    historyRequests[2].complete();
    fixture.detectChanges();
    expect(fixture.componentInstance.anomalyScore).toBe(0.82);
    expect(fixture.componentInstance.anomalyStatus).toBe('ANOMALOUS');
    fixture.destroy();
  });

  it('shows NORMAL only when an anomaly prediction in history explicitly says normal', async () => {
    const drive: DriveDetail = {
      id: '00000000-0000-0000-0000-000000000888',
      name: 'Normal anomaly assessment',
      identifier: 'NORMAL-888',
      model: '', vendor: '', datacenter: '', status: 'HEALTHY', risk_level: null, risk_score: null,
      scored_until: null, is_anomalous: false, anomaly_evaluated: true, last_reading: null,
      attributes: {}, created_at: '', updated_at: '',
    };
    const prediction: DrivePredictionHistoryItem = {
      id: 88,
      prediction_type: 'ANOMALY_DETECTION',
      score: 0.01,
      risk_level: null,
      is_anomalous: false,
      horizon_days: null,
      window_start: '2026-11-01T00:00:00Z',
      window_end: '2026-11-20T00:00:00Z',
      created_at: '2026-11-20T00:01:00Z',
      model: { name: 'LSTM AE', version: 'v1', model_type: 'ANOMALY_DETECTION', architecture: 'LSTM_AUTOENCODER' },
    };
    await TestBed.configureTestingModule({
      imports: [DriveDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: drive.id })) } },
        { provide: DriveService, useValue: { getDrive: () => of(drive), getTelemetry: () => NEVER, getPredictionHistory: () => of([prediction]), getTimeline: () => of(emptyTimeline) } },
        { provide: PredictionService, useValue: { runPrediction: () => NEVER } },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => false } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(DriveDetailComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.componentInstance.anomalyStatus).toBe('NORMAL');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('0.010');
  });

  it('reloads all drive data on route ID changes and ignores late responses from the previous drive', async () => {
    const firstId = '00000000-0000-0000-0000-000000000101';
    const secondId = '00000000-0000-0000-0000-000000000202';
    const routeParams = new BehaviorSubject(convertToParamMap({ id: firstId }));
    const driveRequests = new Map<string, Subject<DriveDetail>>();
    const telemetryRequests = new Map<string, Subject<DriveTelemetryData>>();
    const historyRequests = new Map<string, Subject<DrivePredictionHistoryItem[]>>();
    const getDrive = vi.fn((id: string) => {
      const request = new Subject<DriveDetail>();
      driveRequests.set(id, request);
      return request;
    });
    const getTelemetry = vi.fn((id: string) => {
      const request = new Subject<DriveTelemetryData>();
      telemetryRequests.set(id, request);
      return request;
    });
    const getPredictionHistory = vi.fn((id: string) => {
      const request = new Subject<DrivePredictionHistoryItem[]>();
      historyRequests.set(id, request);
      return request;
    });
    const getTimeline = vi.fn((_id: string) => of(emptyTimeline));
    const drive = (id: string, name: string): DriveDetail => ({
      id, name, identifier: name, model: '', vendor: '', datacenter: '', status: 'HEALTHY',
      risk_level: null, risk_score: null, scored_until: null, is_anomalous: false,
      anomaly_evaluated: true, last_reading: null, attributes: {}, created_at: '', updated_at: '',
    });
    const anomaly = (id: number, score: number): DrivePredictionHistoryItem => ({
      id, prediction_type: 'ANOMALY_DETECTION', score, risk_level: null, is_anomalous: true,
      horizon_days: null, window_start: '', window_end: '', created_at: '',
      model: { name: 'LSTM AE', version: 'v1', model_type: 'ANOMALY_DETECTION', architecture: 'LSTM_AUTOENCODER' },
    });
    const telemetry = (label: string): DriveTelemetryData => ({
      smart: { labels: [label], series: [] }, risk: { labels: [], scores: [] }, thresholds: {},
    });

    await TestBed.configureTestingModule({
      imports: [DriveDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap: routeParams.asObservable() } },
        {
          provide: DriveService,
          useValue: { getDrive, getTelemetry, getPredictionHistory, getTimeline },
        },
        { provide: PredictionService, useValue: { runPrediction: () => NEVER } },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => false } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(DriveDetailComponent);
    fixture.detectChanges();
    expect(fixture.componentInstance.driveId).toBe(firstId);
    expect(getDrive).toHaveBeenLastCalledWith(firstId);
    expect(getTelemetry).toHaveBeenLastCalledWith(firstId, 90);
    expect(getPredictionHistory).toHaveBeenLastCalledWith(firstId);

    driveRequests.get(firstId)!.next(drive(firstId, 'First drive'));
    driveRequests.get(firstId)!.complete();
    fixture.detectChanges();
    telemetryRequests.get(firstId)!.next(telemetry('first-drive-data'));
    telemetryRequests.get(firstId)!.complete();
    historyRequests.get(firstId)!.next([anomaly(1, 0.11)]);
    historyRequests.get(firstId)!.complete();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.componentInstance.drive?.id).toBe(firstId);
    expect((fixture.nativeElement as HTMLElement).querySelector('.drive-title')?.textContent).toContain('First drive');
    expect(getTimeline).toHaveBeenLastCalledWith(firstId, expect.anything());
    expect(fixture.componentInstance.anomalyScore).toBe(0.11);

    routeParams.next(convertToParamMap({ id: secondId }));
    fixture.detectChanges();
    expect(fixture.componentInstance.driveId).toBe(secondId);
    expect(getDrive).toHaveBeenLastCalledWith(secondId);
    expect(getTelemetry).toHaveBeenLastCalledWith(secondId, 90);
    expect(getPredictionHistory).toHaveBeenLastCalledWith(secondId);
    expect(fixture.componentInstance.drive).toBeNull();
    expect(fixture.componentInstance.predictionHistory).toEqual([]);

    driveRequests.get(secondId)!.next(drive(secondId, 'Second drive'));
    driveRequests.get(secondId)!.complete();
    fixture.detectChanges();
    expect(getTimeline).toHaveBeenLastCalledWith(secondId, expect.anything());
    telemetryRequests.get(secondId)!.next(telemetry('second-drive-data'));
    telemetryRequests.get(secondId)!.complete();
    historyRequests.get(secondId)!.next([anomaly(2, 0.82)]);
    historyRequests.get(secondId)!.complete();
    await fixture.whenStable();
    fixture.detectChanges();

    // These subjects model responses that arrive late after switchMap has unsubscribed them.
    driveRequests.get(firstId)!.next(drive(firstId, 'Stale first drive'));
    telemetryRequests.get(firstId)!.next(telemetry('stale-first-data'));
    historyRequests.get(firstId)!.next([anomaly(3, 0.99)]);
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).querySelector('.drive-title')?.textContent).toContain('Second drive');
    expect(fixture.componentInstance.drive?.id).toBe(secondId);
    expect(fixture.componentInstance.telemetryData?.smart.labels).toEqual(['second-drive-data']);
    expect(fixture.componentInstance.anomalyScore).toBe(0.82);
    expect(getTimeline.mock.calls.map(([id]) => id)).toEqual([firstId, secondId]);
    fixture.destroy();
  });

  it('ignores an in-flight scoring response after navigation to another drive', async () => {
    const firstId = '00000000-0000-0000-0000-000000000301';
    const secondId = '00000000-0000-0000-0000-000000000302';
    const routeParams = new BehaviorSubject(convertToParamMap({ id: firstId }));
    const pendingScore = new Subject<PredictionRunResponse>();
    const getDrive = vi.fn((id: string) => of({
      id, name: `Drive ${id}`, identifier: id, model: '', vendor: '', datacenter: '',
      status: 'HEALTHY' as const, risk_level: null, risk_score: null, scored_until: null,
      is_anomalous: false, anomaly_evaluated: false, last_reading: null, attributes: {},
      created_at: '', updated_at: '',
    }));
    const getTelemetry = vi.fn(() => NEVER);
    const getPredictionHistory = vi.fn(() => of([]));
    const getTimeline = vi.fn(() => of(emptyTimeline));
    const runPrediction = vi.fn(() => pendingScore.asObservable());

    await TestBed.configureTestingModule({
      imports: [DriveDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap: routeParams.asObservable() } },
        { provide: DriveService, useValue: { getDrive, getTelemetry, getPredictionHistory, getTimeline } },
        { provide: PredictionService, useValue: { runPrediction } },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => true } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(DriveDetailComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const component = fixture.componentInstance;
    const initialTimelineCalls = getTimeline.mock.calls.length;

    component.onScoreDrive();
    expect(runPrediction).toHaveBeenCalledWith(firstId);
    expect(component.scoring).toBe(true);

    routeParams.next(convertToParamMap({ id: secondId }));
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(component.drive?.id).toBe(secondId);
    expect(component.scoring).toBe(false);
    expect(component.scoreMessage).toBe('');
    expect(component.scoreError).toBe(false);

    const driveCallsAfterNavigation = getDrive.mock.calls.length;
    const telemetryCallsAfterNavigation = getTelemetry.mock.calls.length;
    const historyCallsAfterNavigation = getPredictionHistory.mock.calls.length;
    const timelineCallsAfterNavigation = getTimeline.mock.calls.length;
    expect(timelineCallsAfterNavigation).toBe(initialTimelineCalls + 1);

    pendingScore.next({
      outcome: 'full_success',
      scored_count: 1,
      results: [{
        resource_id: firstId, identifier: firstId, risk_score: 0.98, risk_level: 'CRITICAL',
        is_anomalous: true, anomaly_score: 1.2, window_start: '2026-11-01T00:00:00Z',
        window_end: '2026-11-15T00:00:00Z',
      }],
      errors: [],
    });
    pendingScore.complete();
    fixture.detectChanges();

    expect(component.drive?.id).toBe(secondId);
    expect(component.scoring).toBe(false);
    expect(component.scoreMessage).toBe('');
    expect(component.scoreError).toBe(false);
    expect((fixture.nativeElement as HTMLElement).querySelector('.score-alert')).toBeNull();
    expect(getDrive).toHaveBeenCalledTimes(driveCallsAfterNavigation);
    expect(getTelemetry).toHaveBeenCalledTimes(telemetryCallsAfterNavigation);
    expect(getPredictionHistory).toHaveBeenCalledTimes(historyCallsAfterNavigation);
    expect(getTimeline).toHaveBeenCalledTimes(timelineCallsAfterNavigation);
    fixture.destroy();
  });

  it('shows an explicit not-found state for an invalid drive id', async () => {
    await TestBed.configureTestingModule({
      imports: [DriveDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: 'not-a-uuid' })) } },
        {
          provide: DriveService,
          useValue: {
            getDrive: () => throwError(() => ({ status: 404 })),
            getTelemetry: () => NEVER,
            getPredictionHistory: () => NEVER,
            getTimeline: () => of(emptyTimeline),
          },
        },
        { provide: PredictionService, useValue: { runPrediction: () => NEVER } },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => false } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(DriveDetailComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')?.textContent).toContain('Drive not found.');
  });
});
