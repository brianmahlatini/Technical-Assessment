/**
 * Angular entry point.
 *
 * The frontend is intentionally small and standalone: one bootstrapped component
 * owns routing, API calls, and simple form state for the four required views.
 * This keeps the assessment focused on correctness without hiding behaviour in
 * generated modules.
 */
import { CommonModule } from '@angular/common';
import { HttpClient, HttpClientModule, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Component, importProvidersFrom, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { bootstrapApplication } from '@angular/platform-browser';
import { RouterLink, RouterOutlet, Routes, provideRouter } from '@angular/router';

const API_BASE_URL = 'http://localhost:8000/api/v1';

interface PageMeta {
  page: number;
  page_size: number;
  total: number;
}

interface Medicine {
  code: string;
  name: string;
  form: string;
  strength_value: string;
  strength_unit: string;
  is_active: boolean;
}

interface Rule {
  id: number;
  effective_from: string;
  effective_to: string | null;
  max_quantity_per_dispense: number;
  max_quantity_per_30_days: number;
  requires_authorisation: boolean;
  version_label: string;
}

interface Dispense {
  id: number;
  medicine_code: string;
  medicine_name: string;
  patient_ref: string;
  quantity: number;
  dispensed_at: string;
  authorisation_ref: string | null;
  idempotency_key: string;
}

interface ApiErrorDetail {
  field: string;
  code: string;
  message: string;
  meta?: Record<string, unknown>;
}

class ApiClient {
  private readonly http = inject(HttpClient);

  /** Search endpoint wrapper shared by the catalogue view. */
  searchMedicines(q: string, page: number) {
    const params = new HttpParams().set('q', q).set('page', page).set('page_size', 20);
    return this.http.get<{ data: Medicine[]; meta: PageMeta }>(`${API_BASE_URL}/medicines`, { params });
  }

  /** Medicine detail endpoint wrapper used before loading rule history. */
  getMedicine(code: string) {
    return this.http.get<{ medicine: Medicine; current_rule: Rule | null }>(`${API_BASE_URL}/medicines/${code}`);
  }

  /** Rule history endpoint used to render the timeline. */
  getRules(code: string) {
    return this.http.get<{ data: Rule[] }>(`${API_BASE_URL}/medicines/${code}/rules`);
  }

  /** Idempotent dispense submission wrapper. */
  createDispense(payload: Record<string, unknown>) {
    return this.http.post<Dispense>(`${API_BASE_URL}/dispenses`, payload);
  }

  /** Newest-first patient ledger endpoint wrapper. */
  getLedger(patientRef: string, page: number) {
    const params = new HttpParams().set('patient_ref', patientRef).set('page', page).set('page_size', 20);
    return this.http.get<{ data: Dispense[]; meta: PageMeta }>(`${API_BASE_URL}/dispenses`, { params });
  }
}

@Component({
  standalone: true,
  selector: 'app-shell',
  imports: [CommonModule, RouterLink, RouterOutlet],
  template: `
    <header class="topbar">
      <a routerLink="/" class="brand">EMGuidance Formulary</a>
      <nav>
        <a routerLink="/">Medicines</a>
        <a routerLink="/dispense">Capture</a>
        <a routerLink="/ledger">Ledger</a>
      </nav>
    </header>
    <main>
      <router-outlet></router-outlet>
    </main>
  `
})
class ShellComponent {}

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <section class="panel">
      <h1>Medicine Search</h1>
      <form class="toolbar" (ngSubmit)="load(1)">
        <input name="q" [(ngModel)]="q" placeholder="Search by code or name">
        <button type="submit">Search</button>
      </form>
      <table>
        <thead><tr><th>Code</th><th>Name</th><th>Strength</th><th>Status</th></tr></thead>
        <tbody>
          <tr *ngFor="let medicine of medicines">
            <td><a [routerLink]="['/medicines', medicine.code]">{{ medicine.code }}</a></td>
            <td>{{ medicine.name }}</td>
            <td>{{ medicine.strength_value }} {{ medicine.strength_unit }} {{ medicine.form }}</td>
            <td>{{ medicine.is_active ? 'Active' : 'Inactive' }}</td>
          </tr>
        </tbody>
      </table>
      <div class="pager">
        <button (click)="load(meta.page - 1)" [disabled]="meta.page <= 1">Previous</button>
        <span>Page {{ meta.page }} of {{ totalPages() }}</span>
        <button (click)="load(meta.page + 1)" [disabled]="meta.page >= totalPages()">Next</button>
      </div>
    </section>
  `
})
class MedicineSearchComponent {
  private readonly api = inject(ApiClient);
  q = '';
  medicines: Medicine[] = [];
  meta: PageMeta = { page: 1, page_size: 20, total: 0 };

  constructor() {
    this.load(1);
  }

  /** Loads one catalogue page and keeps pagination state with the result. */
  load(page: number) {
    if (page < 1) return;
    this.api.searchMedicines(this.q, page).subscribe((result) => {
      this.medicines = result.data;
      this.meta = result.meta;
    });
  }

  totalPages() {
    return Math.max(1, Math.ceil(this.meta.total / this.meta.page_size));
  }
}

@Component({
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="panel" *ngIf="medicine">
      <h1>{{ medicine.name }}</h1>
      <p class="muted">{{ medicine.code }} · {{ medicine.strength_value }} {{ medicine.strength_unit }} {{ medicine.form }}</p>
      <p>Current rule: <strong>{{ currentRule ? currentRule.version_label : 'None in force' }}</strong></p>
      <h2>Rule Timeline</h2>
      <ol class="timeline">
        <li *ngFor="let rule of rules" [class.current]="rule.id === currentRule?.id">
          <strong>{{ rule.version_label }}</strong>
          <span>{{ rule.effective_from | date:'medium' }} to {{ rule.effective_to ? (rule.effective_to | date:'medium') : 'open ended' }}</span>
          <small>Per dispense {{ rule.max_quantity_per_dispense }}, 30 days {{ rule.max_quantity_per_30_days }}, auth {{ rule.requires_authorisation ? 'required' : 'not required' }}</small>
        </li>
      </ol>
    </section>
  `
})
class MedicineDetailComponent {
  private readonly api = inject(ApiClient);
  medicine: Medicine | null = null;
  currentRule: Rule | null = null;
  rules: Rule[] = [];

  constructor() {
    const code = location.pathname.split('/').pop() ?? '';
    this.api.getMedicine(code).subscribe((result) => {
      this.medicine = result.medicine;
      this.currentRule = result.current_rule;
    });
    this.api.getRules(code).subscribe((result) => {
      this.rules = result.data;
    });
  }
}

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="panel">
      <h1>Dispense Capture</h1>
      <form class="grid-form" (ngSubmit)="submit()">
        <label>Medicine code<input name="medicine_code" [(ngModel)]="form.medicine_code"></label>
        <label>Patient ref<input name="patient_ref" [(ngModel)]="form.patient_ref"></label>
        <label>Quantity<input name="quantity" type="number" [(ngModel)]="form.quantity"></label>
        <label>Dispensed at<input name="dispensed_at" type="datetime-local" [(ngModel)]="form.dispensed_at"></label>
        <label>Authorisation ref<input name="authorisation_ref" [(ngModel)]="form.authorisation_ref"></label>
        <label>Idempotency key<input name="idempotency_key" [(ngModel)]="form.idempotency_key"></label>
        <button type="submit">Submit Dispense</button>
      </form>
      <div class="success" *ngIf="created">Dispense {{ created.id }} accepted for {{ created.patient_ref }}.</div>
      <div class="errors" *ngIf="errors.length">
        <div *ngFor="let error of errors"><strong>{{ error.field }}</strong>: {{ error.message }}</div>
      </div>
    </section>
  `
})
class DispenseCaptureComponent {
  private readonly api = inject(ApiClient);
  created: Dispense | null = null;
  errors: ApiErrorDetail[] = [];
  form = {
    medicine_code: '',
    patient_ref: '',
    quantity: 1,
    dispensed_at: new Date().toISOString().slice(0, 16),
    authorisation_ref: '',
    idempotency_key: crypto.randomUUID()
  };

  /** Sends the form and renders every server-side rejection reason. */
  submit() {
    this.created = null;
    this.errors = [];
    this.api.createDispense(this.form).subscribe({
      next: (result) => {
        this.created = result;
        this.form.idempotency_key = crypto.randomUUID();
      },
      error: (error: HttpErrorResponse) => {
        this.errors = error.error?.details ?? [{ field: 'request', code: 'failed', message: error.error?.message ?? 'Request failed' }];
      }
    });
  }
}

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="panel">
      <h1>Patient Ledger</h1>
      <form class="toolbar" (ngSubmit)="load(1)">
        <input name="patient_ref" [(ngModel)]="patientRef" placeholder="patient-0001">
        <button type="submit">Load Ledger</button>
      </form>
      <table>
        <thead><tr><th>When</th><th>Medicine</th><th>Quantity</th><th>Auth</th></tr></thead>
        <tbody>
          <tr *ngFor="let row of rows">
            <td>{{ row.dispensed_at | date:'medium' }}</td>
            <td>{{ row.medicine_code }} · {{ row.medicine_name }}</td>
            <td>{{ row.quantity }}</td>
            <td>{{ row.authorisation_ref || 'None' }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  `
})
class PatientLedgerComponent {
  private readonly api = inject(ApiClient);
  patientRef = '';
  rows: Dispense[] = [];

  /** Loads a newest-first patient ledger page from the backend. */
  load(page: number) {
    if (!this.patientRef.trim()) return;
    this.api.getLedger(this.patientRef, page).subscribe((result) => {
      this.rows = result.data;
    });
  }
}

const routes: Routes = [
  { path: '', component: MedicineSearchComponent },
  { path: 'medicines/:code', component: MedicineDetailComponent },
  { path: 'dispense', component: DispenseCaptureComponent },
  { path: 'ledger', component: PatientLedgerComponent }
];

bootstrapApplication(ShellComponent, {
  providers: [ApiClient, provideRouter(routes), importProvidersFrom(HttpClientModule)]
});

