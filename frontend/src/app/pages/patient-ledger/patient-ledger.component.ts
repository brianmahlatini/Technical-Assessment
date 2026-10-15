import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiClient } from '../../core/api-client.service';
import { Dispense } from '../../core/api.models';

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
            <td>{{ row.medicine_code }} - {{ row.medicine_name }}</td>
            <td>{{ row.quantity }}</td>
            <td>{{ row.authorisation_ref || 'None' }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  `
})
export class PatientLedgerComponent {
  private readonly api = inject(ApiClient);

  patientRef = '';
  rows: Dispense[] = [];

  load(page: number) {
    if (!this.patientRef.trim()) {
      return;
    }

    this.api.getLedger(this.patientRef, page).subscribe((result) => {
      this.rows = result.data;
    });
  }
}

