import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NEVER, of } from 'rxjs';
import { DriveDetail } from '../../../core/models/drive.models';
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
        { provide: DriveService, useValue: { getDrive: () => of(drive), getTelemetry: () => NEVER } },
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
  });
});
