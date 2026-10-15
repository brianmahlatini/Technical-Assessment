/*
 * Patient ledger page.
 *
 * Why this file exists:
 *   This standalone component lets reviewers inspect dispense history for an
 *   opaque patient reference, using the seeded dataset and the backend ledger
 *   endpoint.
 */

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
  // Shared API client hides URL/query-string details from the component.
  private readonly api = inject(ApiClient);

  // User-entered opaque patient reference, for example `patient-0001`.
  patientRef = '';

  // Current ledger rows returned by the backend.
  rows: Dispense[] = [];

  load(page: number) {
    // Avoid unnecessary API calls when the input is blank.
    if (!this.patientRef.trim()) {
      return;
    }

    // Replace the ledger rows from the backend response so the table always
    // reflects the selected patient reference.
    this.api.getLedger(this.patientRef, page).subscribe((result) => {
      this.rows = result.data;
    });
  }
}

