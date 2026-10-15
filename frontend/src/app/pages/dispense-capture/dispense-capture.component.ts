import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiClient } from '../../core/api-client.service';
import { ApiErrorDetail, Dispense, DispenseFormPayload } from '../../core/api.models';

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
export class DispenseCaptureComponent {
  private readonly api = inject(ApiClient);

  created: Dispense | null = null;
  errors: ApiErrorDetail[] = [];
  form: DispenseFormPayload = {
    medicine_code: '',
    patient_ref: '',
    quantity: 1,
    dispensed_at: new Date().toISOString().slice(0, 16),
    authorisation_ref: '',
    idempotency_key: crypto.randomUUID()
  };

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

