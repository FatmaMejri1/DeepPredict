import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  DashboardActivityResponse,
  DashboardSummary,
  InferenceServiceHealth,
} from '../models/dashboard.models';

@Injectable({
  providedIn: 'root',
})
export class DashboardService {
  private http = inject(HttpClient);

  getSummary(): Observable<DashboardSummary> {
    return this.http.get<DashboardSummary>(`${environment.apiUrl}/dashboard/summary/`);
  }

  getRecentActivity(): Observable<DashboardActivityResponse> {
    return this.http.get<DashboardActivityResponse>(`${environment.apiUrl}/dashboard/activity/`);
  }

  getInferenceHealth(): Observable<InferenceServiceHealth> {
    return this.http.get<InferenceServiceHealth>(`${environment.apiUrl}/dashboard/health/`);
  }
}
