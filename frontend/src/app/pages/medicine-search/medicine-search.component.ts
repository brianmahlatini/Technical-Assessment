/*
 * Medicine search page.
 *
 * Why this file exists:
 *   This standalone component implements the catalogue view required by the
 *   assessment. It owns search input, pagination state, and links into the
 *   medicine detail route.
 */

import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApiClient } from '../../core/api-client.service';
import { Medicine, PageMeta } from '../../core/api.models';

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
        <button type="button" (click)="load(meta.page - 1)" [disabled]="meta.page <= 1">Previous</button>
        <span>Page {{ meta.page }} of {{ totalPages() }}</span>
        <button type="button" (click)="load(meta.page + 1)" [disabled]="meta.page >= totalPages()">Next</button>
      </div>
    </section>
  `
})
export class MedicineSearchComponent {
  // Keep API access behind the shared client so this page only manages view state.
  private readonly api = inject(ApiClient);

  // Search term typed by the user. Empty string loads the default catalogue.
  q = '';

  // Current page of medicines returned by the backend.
  medicines: Medicine[] = [];

  // Pagination metadata mirrors the backend response and drives pager buttons.
  meta: PageMeta = { page: 1, page_size: 20, total: 0 };

  constructor() {
    // Load the first page immediately so the user lands on useful seeded data.
    this.load(1);
  }

  load(page: number) {
    // Guard against accidental calls before page one.
    if (page < 1) {
      return;
    }

    // Replace local state only after the backend returns so the table and pager
    // stay consistent with the same response.
    this.api.searchMedicines(this.q, page).subscribe((result) => {
      this.medicines = result.data;
      this.meta = result.meta;
    });
  }

  totalPages() {
    // Always show at least one page so the pager remains stable when there are
    // no results.
    return Math.max(1, Math.ceil(this.meta.total / this.meta.page_size));
  }
}

