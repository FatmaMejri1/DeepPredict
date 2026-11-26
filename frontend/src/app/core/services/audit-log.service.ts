import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuditLogFilters, AuditLogPage } from '../models/audit-log.models';

@Injectable({ providedIn: 'root' })
export class AuditLogService {
  private http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/audit-logs/`;

  getAuditLogs(filters: AuditLogFilters = {}, page = 1, pageSize = 25): Observable<AuditLogPage> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    if (filters.username?.trim()) params = params.set('username', filters.username.trim());
    if (filters.action) params = params.set('action', filters.action);
    if (filters.date_from) params = params.set('date_from', filters.date_from);
    if (filters.date_to) params = params.set('date_to', filters.date_to);
    return this.http.get<AuditLogPage>(this.url, { params });
  }
}
