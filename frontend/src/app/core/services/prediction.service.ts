import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { PredictionRunResponse } from '../models/prediction.models';

@Injectable({
  providedIn: 'root',
})
export class PredictionService {
  private http = inject(HttpClient);

  runPrediction(resourceId?: string): Observable<PredictionRunResponse> {
    const payload = resourceId ? { resource_id: resourceId } : {};
    return this.http.post<PredictionRunResponse>(`${environment.apiUrl}/predictions/predict/`, payload);
  }
}
