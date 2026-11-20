import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NEVER, of } from 'rxjs';
import { DriveDetail, DrivePredictionHistoryItem } from '../../../core/models/drive.models';
import { AuthService } from '../../../core/services/auth.service';
import { DriveService } from '../../../core/services/drive.service';
import { PredictionService } from '../../../core/services/prediction.service';
import { DriveDetailComponent } from './drive-detail.component';

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
      last_reading: null,
      attributes: {},
      created_at: '2026-11-20T00:00:00Z',
      updated_at: '2026-11-20T00:00:00Z',
    };
    await TestBed.configureTestingModule({
      imports: [DriveDetailComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ id: drive.id }) } } },
        { provide: DriveService, useValue: { getDrive: () => of(drive), getTelemetry: () => NEVER, getPredictionHistory: () => of([]) } },
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
    expect(element.textContent).toContain('No predictions yet for this drive.');
  });

  it('renders prediction timestamps, type, score and model version in history', async () => {
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
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ id: drive.id }) } } },
        {
          provide: DriveService,
          useValue: { getDrive: () => of(drive), getTelemetry: () => NEVER, getPredictionHistory: () => of([prediction]) },
        },
        { provide: PredictionService, useValue: { runPrediction: () => NEVER } },
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => false } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(DriveDetailComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const history = fixture.nativeElement.querySelector('.history-table') as HTMLTableElement;

    expect(history.textContent).toContain('Failure risk');
    expect(history.textContent).toContain('HIGH');
    expect(history.textContent).toContain('0.820');
    expect(history.textContent).toContain('Risk GRU');
    expect(history.textContent).toContain('v2');
    expect(history.textContent).toContain('Nov 19, 2026');
  });
});
