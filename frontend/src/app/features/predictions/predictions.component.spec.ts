import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { ModelService } from '../../core/services/model.service';
import { PredictionService } from '../../core/services/prediction.service';
import { PredictionsComponent } from './predictions.component';

describe('PredictionsComponent', () => {
  it('communicates full and partial prediction outcomes distinctly', async () => {
    const predictionResponse = new Subject<any>();
    await TestBed.configureTestingModule({
      imports: [PredictionsComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => true } },
        { provide: PredictionService, useValue: { runPrediction: () => predictionResponse } },
        { provide: ModelService, useValue: { getModels: () => of([]) } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(PredictionsComponent);
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.header-action button') as HTMLButtonElement).click();
    predictionResponse.next({ outcome: 'full_success', scored_count: 2, results: [], errors: [] });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.componentInstance.lastResponse?.outcome).toBe('full_success');
    expect(fixture.nativeElement.querySelector('.execution-outcome')?.textContent)
      .toContain('All requested drives were scored successfully.');
    expect(fixture.nativeElement.querySelector('.execution-outcome')?.classList.contains('outcome-success')).toBe(true);

    (fixture.nativeElement.querySelector('.header-action button') as HTMLButtonElement).click();
    predictionResponse.next({
      outcome: 'partial_success',
      scored_count: 1,
      results: [],
      errors: [{ resource_id: 'drive-2', identifier: 'DRIVE-2', code: 'insufficient_history', error: 'Insufficient valid telemetry history for prediction.' }],
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.execution-outcome')?.textContent)
      .toContain('Partial success: 1 drives scored; 1 could not be scored.');
    expect(fixture.nativeElement.querySelector('.execution-outcome')?.classList.contains('outcome-partial')).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('Insufficient valid telemetry history for prediction.');
    expect(fixture.nativeElement.textContent).toContain('SKIPPED');
    fixture.destroy();
  });

  it('renders a structured complete failure returned with an HTTP error status', async () => {
    const failure = {
      outcome: 'complete_failure',
      message: 'No drives were successfully scored. Review the per-drive results and try again.',
      scored_count: 0,
      results: [],
      errors: [{ resource_id: 'drive-1', identifier: 'DRIVE-1', code: 'internal_error', error: 'Prediction could not be completed due to an internal error.' }],
    };
    await TestBed.configureTestingModule({
      imports: [PredictionsComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => true } },
        { provide: PredictionService, useValue: { runPrediction: () => throwError(() => ({ status: 500, error: failure })) } },
        { provide: ModelService, useValue: { getModels: () => of([]) } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(PredictionsComponent);
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.header-action button') as HTMLButtonElement).click();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.componentInstance.lastResponse?.outcome).toBe('complete_failure');
    expect(fixture.nativeElement.querySelector('.execution-outcome')?.textContent).toContain(failure.message);
    expect(fixture.nativeElement.querySelector('.execution-outcome')?.classList.contains('outcome-failure')).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('Prediction could not be completed due to an internal error.');
    expect(fixture.nativeElement.textContent).toContain('FAILED');
    expect(fixture.nativeElement.textContent).not.toContain('database password');
    fixture.destroy();
  });

  it('shows a generic safe message for an unstructured prediction request failure', async () => {
    await TestBed.configureTestingModule({
      imports: [PredictionsComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => true } },
        { provide: PredictionService, useValue: { runPrediction: () => throwError(() => new Error('private backend detail')) } },
        { provide: ModelService, useValue: { getModels: () => of([]) } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(PredictionsComponent);
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.header-action button') as HTMLButtonElement).click();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.componentInstance.runErrorMessage).toBe('The prediction request could not be completed. Please try again.');
    expect(fixture.nativeElement.querySelector('[role="alert"]')?.textContent)
      .toContain('The prediction request could not be completed. Please try again.');
    expect(fixture.nativeElement.textContent).not.toContain('private backend detail');
    fixture.destroy();
  });

  it('shows active risk and anomaly thresholds from the model API', async () => {
    await TestBed.configureTestingModule({
      imports: [PredictionsComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => true } },
        { provide: PredictionService, useValue: { runPrediction: () => of({ scored_count: 0, results: [], errors: [] }) } },
        {
          provide: ModelService,
          useValue: {
            getModels: () => of([
              { model_type: 'FAILURE_PREDICTION', is_active: true, thresholds: { medium: 0.44, high: 0.71 } },
              { model_type: 'ANOMALY_DETECTION', is_active: true, thresholds: { anomaly: 0.08 } },
            ]),
          },
        },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(PredictionsComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('MEDIUM (0.44)');
    expect(text).toContain('HIGH (0.71)');
    expect(text).toContain('ANOMALY (0.08)');
    expect(text).not.toContain('0.35');
    expect(text).not.toContain('0.05');
  });

  it('clearly reports thresholds when there is no active model configuration', async () => {
    await TestBed.configureTestingModule({
      imports: [PredictionsComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { isITProOrSysAdmin: () => false } },
        { provide: PredictionService, useValue: { runPrediction: () => of({ scored_count: 0, results: [], errors: [] }) } },
        { provide: ModelService, useValue: { getModels: () => of([]) } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(PredictionsComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Active model thresholds: Unavailable');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Active model threshold: Unavailable');
  });
});
