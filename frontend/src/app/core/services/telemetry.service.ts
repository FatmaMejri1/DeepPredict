import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { TelemetryUploadResponse, ValidationReport } from '../models/telemetry.models';

@Injectable({
  providedIn: 'root',
})
export class TelemetryService {
  private http = inject(HttpClient);

  validateFile(file: File): Observable<ValidationReport> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<ValidationReport>(`${environment.apiUrl}/telemetry/validate/`, formData);
  }

  validateReadings(readings: any[]): Observable<ValidationReport> {
    return this.http.post<ValidationReport>(`${environment.apiUrl}/telemetry/validate/`, { readings });
  }

  uploadFile(file: File, resourceId?: string): Observable<TelemetryUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (resourceId) {
      formData.append('resource_id', resourceId);
    }
    return this.http.post<TelemetryUploadResponse>(`${environment.apiUrl}/telemetry/upload/`, formData);
  }

  uploadReadings(readings: any[], resourceId?: string): Observable<TelemetryUploadResponse> {
    return this.http.post<TelemetryUploadResponse>(`${environment.apiUrl}/telemetry/upload/`, {
      readings,
      resource_id: resourceId,
    });
  }
}
