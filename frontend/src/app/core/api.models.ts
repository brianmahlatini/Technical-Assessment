/*
 * Shared API TypeScript models.
 *
 * Why this file exists:
 *   These interfaces mirror the backend response/request shapes used by the
 *   Angular components. Keeping them in one core file avoids each page inventing
 *   its own partial copy of the API contract.
 */

// Pagination metadata appears on medicine search and ledger list responses.
export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
}

// Medicine rows power the search results and the detail page header.
export interface Medicine {
  code: string;
  name: string;
  form: string;
  strength_value: string;
  strength_unit: string;
  is_active: boolean;
}

// Rule rows power the medicine detail timeline and current-rule display.
export interface Rule {
  id: number;
  effective_from: string;
  effective_to: string | null;
  max_quantity_per_dispense: number;
  max_quantity_per_30_days: number;
  requires_authorisation: boolean;
  version_label: string;
}

// Dispense rows are returned for accepted submissions and patient ledger items.
export interface Dispense {
  id: number;
  medicine_code: string;
  medicine_name: string;
  patient_ref: string;
  quantity: number;
  dispensed_at: string;
  authorisation_ref: string | null;
  idempotency_key: string;
}

// Backend business validation details map directly to form-level messages.
export interface ApiErrorDetail {
  field: string;
  code: string;
  message: string;
  meta?: Record<string, unknown>;
}

// The capture form sends this payload to POST /dispenses.
export interface DispenseFormPayload {
  medicine_code: string;
  patient_ref: string;
  quantity: number;
  dispensed_at: string;
  authorisation_ref: string;
  idempotency_key: string;
}

