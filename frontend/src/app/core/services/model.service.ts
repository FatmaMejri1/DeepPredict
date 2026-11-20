import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { MLModelCard } from '../models/model.models';

@Injectable({
  providedIn: 'root',
})
export class ModelService {
  private http = inject(HttpClient);

  getModels(): Observable<MLModelCard[]> {
    return this.http.get<MLModelCard[]>(`${environment.apiUrl}/ml-models/`);
  }
}
