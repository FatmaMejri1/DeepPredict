import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  DashboardActivityResponse,
  DashboardFilters,
  DashboardSummary,
  InferenceServiceHealth,
} from '../models/dashboard.models';

@Injectable({
  providedIn: 'root',
})
export class DashboardService {
  private http = inject(HttpClient);

  getSummary(filters?: DashboardFilters): Observable<DashboardSummary> {
    return this.http.get<DashboardSummary>(`${environment.apiUrl}/dashboard/summary/`, {
      params: this.buildFilterParams(filters),
    });
  }

  getRecentActivity(filters?: DashboardFilters): Observable<DashboardActivityResponse> {
    return this.http.get<DashboardActivityResponse>(`${environment.apiUrl}/dashboard/activity/`, {
      params: this.buildFilterParams(filters),
    });
  }

  getInferenceHealth(): Observable<InferenceServiceHealth> {
    return this.http.get<InferenceServiceHealth>(`${environment.apiUrl}/dashboard/health/`);
  }

  private buildFilterParams(filters?: DashboardFilters): Record<string, string> {
    const params: Record<string, string> = {};
    if (filters?.status) params['status'] = filters.status;
    if (filters?.risk_level) params['risk_level'] = filters.risk_level;
    if (filters?.is_anomalous) params['is_anomalous'] = filters.is_anomalous;
    return params;
  }
}
