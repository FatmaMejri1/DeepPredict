import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { MLModelCard } from '../../core/models/model.models';
import { ModelService } from '../../core/services/model.service';
import { MlModelsComponent } from './ml-models.component';

describe('MlModelsComponent', () => {
  it('renders the model evaluation protocol, thresholds and benchmark percentages', async () => {
    const model: MLModelCard = {
      id: 'model-risk-1',
      name: 'Risk GRU',
      version: '2.0.0',
      model_type: 'FAILURE_PREDICTION',
      architecture: 'GRU',
      training_dataset: 'Backblaze holdout',
      trained_at: '2026-11-20T00:00:00Z',
      is_active: true,
      thresholds: { medium: 0.35, high: 0.6, critical: 0.8 },
      config: {},
      protocol: 'time-based holdout',
      rows: [{ label: 'HIGH', threshold: 0.6, healthy: 1, failed: 55 }],
      evaluation_metrics: {
        protocol: 'time-based holdout',
        results: { high: { healthy_drives_flagged: 0.01, failed_drives_detected: 0.55 } },
      },
    };
    const anomalyModel: MLModelCard = {
      id: 'model-anomaly-1',
      name: 'Disk anomaly LSTM',
      version: '1.0.0',
      model_type: 'ANOMALY_DETECTION',
      architecture: 'LSTM_AUTOENCODER',
      training_dataset: 'Backblaze normal operations',
      trained_at: '2026-11-20T00:00:00Z',
      is_active: true,
      thresholds: { anomaly: 0.05 },
      config: {},
      protocol: 'normal-only holdout',
      rows: [{ label: 'ANOMALOUS', threshold: 0.05, healthy: 2, failed: 14 }],
      evaluation_metrics: {
        protocol: 'normal-only holdout',
        results: { healthy_drives_flagged: 0.02, failed_drives_detected: 0.14 },
      },
    };
    await TestBed.configureTestingModule({
      imports: [MlModelsComponent],
      providers: [{ provide: ModelService, useValue: { getModels: () => of([model, anomalyModel]) } }],
    }).compileComponents();

    const fixture = TestBed.createComponent(MlModelsComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('Risk GRU');
    expect(text).toContain('Backblaze holdout');
    expect(text).toContain('time-based holdout');
    expect(text).toContain('HIGH');
    expect(text).toContain('0.6');
    expect(text).toContain('55.0%');
    expect(text).toContain('1.00%');
    expect(text).toContain('Disk anomaly LSTM');
    expect(text).toContain('normal-only holdout');
    expect(text).toContain('ANOMALOUS');
    expect(text).toContain('14.0%');
    expect(text).toContain('2.00%');
    expect(text).toContain('NOT an absolute Bayesian probability of failure');
  });
});
