import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Drive, DriveDetail, DrivePredictionHistoryItem, DriveTelemetryData, PaginatedResponse } from '../models/drive.models';

export interface DriveQueryParams {
  search?: string;
  status?: string;
  risk_level?: string;
  is_anomalous?: string;
  ordering?: string;
  page?: number;
  page_size?: number;
}

@Injectable({
  providedIn: 'root',
})
export class DriveService {
  private http = inject(HttpClient);

  getDrives(params?: DriveQueryParams): Observable<PaginatedResponse<Drive>> {
    let httpParams = new HttpParams();
    if (params) {
      if (params.search) httpParams = httpParams.set('search', params.search);
      if (params.status) httpParams = httpParams.set('status', params.status);
      if (params.risk_level) httpParams = httpParams.set('risk_level', params.risk_level);
      if (params.is_anomalous) httpParams = httpParams.set('is_anomalous', params.is_anomalous);
      if (params.ordering) httpParams = httpParams.set('ordering', params.ordering);
      if (params.page) httpParams = httpParams.set('page', params.page.toString());
      if (params.page_size) httpParams = httpParams.set('page_size', params.page_size.toString());
    }
    return this.http.get<PaginatedResponse<Drive>>(`${environment.apiUrl}/drives/`, { params: httpParams });
  }

  getDrive(id: string): Observable<DriveDetail> {
    return this.http.get<DriveDetail>(`${environment.apiUrl}/drives/${id}/`);
  }

  getTelemetry(id: string, days: number = 90): Observable<DriveTelemetryData> {
    const params = new HttpParams().set('days', days.toString());
    return this.http.get<DriveTelemetryData>(`${environment.apiUrl}/drives/${id}/telemetry/`, { params });
  }

  getPredictionHistory(id: string): Observable<DrivePredictionHistoryItem[]> {
    return this.http.get<DrivePredictionHistoryItem[]>(`${environment.apiUrl}/drives/${id}/predictions/`);
  }
}
