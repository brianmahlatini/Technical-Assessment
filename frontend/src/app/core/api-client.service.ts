/*
 * API client service.
 *
 * Why this file exists:
 *   Components should not know raw backend URLs or repeat HTTP request details.
 *   This service centralises API calls so the frontend has one integration
 *   layer between Angular views and the FastAPI backend.
 */

import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

import { Dispense, DispenseFormPayload, Medicine, PageMeta, Rule } from './api.models';

const API_BASE_URL = 'http://localhost:8000/api/v1';

@Injectable({ providedIn: 'root' })
export class ApiClient {
  // Angular injects HttpClient once for this singleton service.
  private readonly http = inject(HttpClient);

  searchMedicines(q: string, page: number) {
    // Query parameters match the backend's pagination contract.
    const params = new HttpParams().set('q', q).set('page', page).set('page_size', 20);
    return this.http.get<{ data: Medicine[]; meta: PageMeta }>(`${API_BASE_URL}/medicines`, { params });
  }

  getMedicine(code: string) {
    // Detail response contains catalogue data plus the currently active rule.
    return this.http.get<{ medicine: Medicine; current_rule: Rule | null }>(`${API_BASE_URL}/medicines/${code}`);
  }

  getRules(code: string) {
    // Rule history powers the timeline shown on the medicine detail page.
    return this.http.get<{ data: Rule[] }>(`${API_BASE_URL}/medicines/${code}/rules`);
  }

  createDispense(payload: DispenseFormPayload) {
    // The backend handles idempotency and returns either a successful dispense
    // body or a structured validation error.
    return this.http.post<Dispense>(`${API_BASE_URL}/dispenses`, payload);
  }

  getLedger(patientRef: string, page: number) {
    // Ledger filtering happens server-side so the UI can request one patient at
    // a time without downloading all dispenses.
    const params = new HttpParams().set('patient_ref', patientRef).set('page', page).set('page_size', 20);
    return this.http.get<{ data: Dispense[]; meta: PageMeta }>(`${API_BASE_URL}/dispenses`, { params });
  }
}

