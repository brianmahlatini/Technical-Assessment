/*
 * Medicine detail page.
 *
 * Why this file exists:
 *   This component shows one medicine plus its current rule and full historical
 *   rule timeline. It stays separate from search because it has different API
 *   calls and page state.
 */

import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

import { ApiClient } from '../../core/api-client.service';
import { ApiErrorDetail, Medicine, Rule, RuleCreatePayload } from '../../core/api.models';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="panel" *ngIf="medicine">
      <div class="page-heading">
        <div>
          <h1>{{ medicine.name }}</h1>
          <p class="muted">{{ medicine.code }} - {{ medicine.strength_value }} {{ medicine.strength_unit }} {{ medicine.form }}</p>
        </div>
        <button type="button" (click)="toggleRuleForm()">{{ showRuleForm ? 'Cancel' : 'Add New Rule' }}</button>
      </div>
      <p>Current rule: <strong>{{ currentRule ? currentRule.version_label : 'None in force' }}</strong></p>

      <form class="grid-form rule-form" *ngIf="showRuleForm" (ngSubmit)="submitRule()">
        <label>Effective from<input name="effective_from" type="datetime-local" [(ngModel)]="ruleForm.effective_from"></label>
        <label>Max per dispense<input name="max_quantity_per_dispense" type="number" min="1" [(ngModel)]="ruleForm.max_quantity_per_dispense"></label>
        <label>Max per 30 days<input name="max_quantity_per_30_days" type="number" min="1" [(ngModel)]="ruleForm.max_quantity_per_30_days"></label>
        <label class="checkbox-label"><input name="requires_authorisation" type="checkbox" [(ngModel)]="ruleForm.requires_authorisation">Requires authorisation</label>
        <button type="submit" [disabled]="savingRule">Save Rule</button>
      </form>

      <div class="success" *ngIf="ruleMessage">{{ ruleMessage }}</div>
      <div class="errors" *ngIf="ruleErrors.length">
        <div *ngFor="let error of ruleErrors"><strong>{{ error.field }}</strong>: {{ error.message }}</div>
      </div>

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

  // Store the route code once because create/reload actions all target the same medicine.
  private readonly code = this.route.snapshot.paramMap.get('code') ?? '';

  // Controls whether the add-rule form is visible.
  showRuleForm = false;

  // Prevents double submission while the POST request is in progress.
  savingRule = false;

  // Short success message shown after the backend accepts a new rule.
  ruleMessage = '';

  // Structured form-level errors shown when the backend rejects the new rule.
  ruleErrors: ApiErrorDetail[] = [];

  // Form state mirrors the backend RuleCreate schema.
  ruleForm: RuleCreatePayload = this.defaultRuleForm();

  constructor() {
    this.loadMedicine();
    this.loadRules();
  }

  loadMedicine() {
    // Fetch summary/detail data independently from timeline data so each API
    // contract remains small and focused.
    this.api.getMedicine(this.code).subscribe((result) => {
      this.medicine = result.medicine;
      this.currentRule = result.current_rule;

      // When the page loads, prefill limits from the current rule so the user
      // only edits the values that are changing.
      this.ruleForm = this.defaultRuleForm();
    });
  }

  loadRules() {
    // Load the full rule history for the timeline.
    this.api.getRules(this.code).subscribe((result) => {
      this.rules = result.data;
    });
  }

  toggleRuleForm() {
    // Reset messages when opening/closing so old results do not look like the
    // current form state.
    this.showRuleForm = !this.showRuleForm;
    this.ruleMessage = '';
    this.ruleErrors = [];
    this.ruleForm = this.defaultRuleForm();
  }

  submitRule() {
    this.savingRule = true;
    this.ruleMessage = '';
    this.ruleErrors = [];

    this.api.createRule(this.code, this.ruleForm).subscribe({
      next: (rule) => {
        this.savingRule = false;
        this.showRuleForm = false;
        this.ruleMessage = `Rule ${rule.version_label} was added.`;
        this.loadMedicine();
        this.loadRules();
      },
      error: (error: HttpErrorResponse) => {
        this.savingRule = false;
        this.ruleErrors = this.errorDetails(error);
      }
    });
  }

  private defaultRuleForm(): RuleCreatePayload {
    // Use local datetime-local format because the browser input expects
    // `YYYY-MM-DDTHH:mm`; the backend normalises naive values to Johannesburg time.
    const localNow = new Date();
    localNow.setMinutes(localNow.getMinutes() - localNow.getTimezoneOffset());

    return {
      effective_from: localNow.toISOString().slice(0, 16),
      max_quantity_per_dispense: this.currentRule?.max_quantity_per_dispense ?? 1,
      max_quantity_per_30_days: this.currentRule?.max_quantity_per_30_days ?? 1,
      requires_authorisation: this.currentRule?.requires_authorisation ?? false
    };
  }

  private errorDetails(error: HttpErrorResponse): ApiErrorDetail[] {
    if (Array.isArray(error.error?.details)) {
      return error.error.details;
    }

    if (Array.isArray(error.error?.detail)) {
      return error.error.detail.map((detail: { loc?: string[]; msg?: string }) => ({
        field: detail.loc?.join('.') ?? 'request',
        code: 'validation_error',
        message: detail.msg ?? 'Invalid rule request.'
      }));
    }

    return [{ field: 'request', code: 'failed', message: error.error?.message ?? 'Rule could not be saved.' }];
  }
}

