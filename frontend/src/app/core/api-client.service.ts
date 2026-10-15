import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

import { Dispense, DispenseFormPayload, Medicine, PageMeta, Rule } from './api.models';

const API_BASE_URL = 'http://localhost:8000/api/v1';

@Injectable({ providedIn: 'root' })
export class ApiClient {
  private readonly http = inject(HttpClient);

  searchMedicines(q: string, page: number) {
    const params = new HttpParams().set('q', q).set('page', page).set('page_size', 20);
    return this.http.get<{ data: Medicine[]; meta: PageMeta }>(`${API_BASE_URL}/medicines`, { params });
  }

  getMedicine(code: string) {
    return this.http.get<{ medicine: Medicine; current_rule: Rule | null }>(`${API_BASE_URL}/medicines/${code}`);
  }

  getRules(code: string) {
    return this.http.get<{ data: Rule[] }>(`${API_BASE_URL}/medicines/${code}/rules`);
  }

  createDispense(payload: DispenseFormPayload) {
    return this.http.post<Dispense>(`${API_BASE_URL}/dispenses`, payload);
  }

  getLedger(patientRef: string, page: number) {
    const params = new HttpParams().set('patient_ref', patientRef).set('page', page).set('page_size', 20);
    return this.http.get<{ data: Dispense[]; meta: PageMeta }>(`${API_BASE_URL}/dispenses`, { params });
  }
}

