import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { BehaviorSubject, Observable, catchError, map, of, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Alert, AlertFilters, AlertPage, AlertUnreadCount } from '../models/alert.models';

@Injectable({ providedIn: 'root' })
export class AlertService {
  private http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/alerts/`;
  private readonly unreadCountSubject = new BehaviorSubject<number | null>(null);
  private unreadCountRequestVersion = 0;
  readonly unreadCount$ = this.unreadCountSubject.asObservable();

  getAlerts(filters: AlertFilters = {}, page = 1, pageSize = 20): Observable<AlertPage> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    if (filters.status) params = params.set('status', filters.status);
    if (filters.alert_type) params = params.set('alert_type', filters.alert_type);
    if (filters.severity) params = params.set('severity', filters.severity);
    if (filters.resource?.trim()) params = params.set('resource', filters.resource.trim());
    return this.http.get<AlertPage>(this.baseUrl, { params });
  }

  getAlert(id: string): Observable<Alert> {
    return this.http.get<Alert>(`${this.baseUrl}${encodeURIComponent(id)}/`);
  }

  getUnreadCount(): Observable<AlertUnreadCount> {
    return this.http.get<AlertUnreadCount>(`${this.baseUrl}unread-count/`);
  }

  refreshUnreadCount(): Observable<number | null> {
    const requestVersion = ++this.unreadCountRequestVersion;
    return this.getUnreadCount().pipe(
      map((response) => requestVersion === this.unreadCountRequestVersion ? response.count : null),
      tap((count) => {
        if (requestVersion === this.unreadCountRequestVersion) this.unreadCountSubject.next(count);
      }),
      catchError(() => {
        if (requestVersion === this.unreadCountRequestVersion) this.unreadCountSubject.next(null);
        return of(null);
      }),
    );
  }

  clearUnreadCount(): void {
    this.unreadCountRequestVersion++;
    this.unreadCountSubject.next(null);
  }

  acknowledge(id: string): Observable<Alert> {
    return this.http.post<Alert>(`${this.baseUrl}${encodeURIComponent(id)}/acknowledge/`, {});
  }

  resolve(id: string): Observable<Alert> {
    return this.http.post<Alert>(`${this.baseUrl}${encodeURIComponent(id)}/resolve/`, {});
  }
}
