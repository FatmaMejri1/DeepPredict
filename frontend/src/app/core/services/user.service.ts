import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { CreateUserPayload, UpdateUserPayload, UserListItem } from '../models/user.models';

@Injectable({
  providedIn: 'root',
})
export class UserService {
  private http = inject(HttpClient);

  getUsers(): Observable<UserListItem[]> {
    return this.http.get<UserListItem[] | { results: UserListItem[] }>(`${environment.apiUrl}/users/`).pipe(
      map((response) => Array.isArray(response) ? response : response.results),
    );
  }

  getUser(id: string): Observable<UserListItem> {
    return this.http.get<UserListItem>(`${environment.apiUrl}/users/${id}/`);
  }

  createUser(payload: CreateUserPayload): Observable<UserListItem> {
    return this.http.post<UserListItem>(`${environment.apiUrl}/users/`, payload);
  }

  updateUser(id: string, payload: UpdateUserPayload): Observable<UserListItem> {
    return this.http.patch<UserListItem>(`${environment.apiUrl}/users/${id}/`, payload);
  }

  activateUser(id: string): Observable<any> {
    return this.http.post(`${environment.apiUrl}/users/${id}/activate/`, {});
  }

  deactivateUser(id: string): Observable<any> {
    return this.http.post(`${environment.apiUrl}/users/${id}/deactivate/`, {});
  }

  setPassword(id: string, password: string): Observable<any> {
    return this.http.post(`${environment.apiUrl}/users/${id}/set-password/`, { password });
  }
}
