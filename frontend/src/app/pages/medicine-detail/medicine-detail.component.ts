/*
 * Medicine detail page.
 *
 * Why this file exists:
 *   This component shows one medicine plus its current rule and full historical
 *   rule timeline. It stays separate from search because it has different API
 *   calls and page state.
 */

import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

import { ApiClient } from '../../core/api-client.service';
import { Medicine, Rule } from '../../core/api.models';

@Component({
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="panel" *ngIf="medicine">
      <h1>{{ medicine.name }}</h1>
      <p class="muted">{{ medicine.code }} - {{ medicine.strength_value }} {{ medicine.strength_unit }} {{ medicine.form }}</p>
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
export class MedicineDetailComponent {
  // Shared API client keeps HTTP details outside the component.
  private readonly api = inject(ApiClient);

  // ActivatedRoute provides the medicine code from `/medicines/:code`.
  private readonly route = inject(ActivatedRoute);

  // Header/details area for the selected medicine.
  medicine: Medicine | null = null;

  // Current active rule, if one is in force at request time.
  currentRule: Rule | null = null;

  // Complete historical timeline rendered underneath the header.
  rules: Rule[] = [];

  constructor() {
    // The route is created only for detail URLs, but the empty fallback keeps
    // the code defensive if routing changes later.
    const code = this.route.snapshot.paramMap.get('code') ?? '';

    // Fetch summary/detail data independently from timeline data so each API
    // contract remains small and focused.
    this.api.getMedicine(code).subscribe((result) => {
      this.medicine = result.medicine;
      this.currentRule = result.current_rule;
    });

    // Load the full rule history for the timeline.
    this.api.getRules(code).subscribe((result) => {
      this.rules = result.data;
    });
  }
}

