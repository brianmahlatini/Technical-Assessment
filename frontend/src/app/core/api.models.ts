export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface Medicine {
  code: string;
  name: string;
  form: string;
  strength_value: string;
  strength_unit: string;
  is_active: boolean;
}

export interface Rule {
  id: number;
  effective_from: string;
  effective_to: string | null;
  max_quantity_per_dispense: number;
  max_quantity_per_30_days: number;
  requires_authorisation: boolean;
  version_label: string;
}

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

export interface ApiErrorDetail {
  field: string;
  code: string;
  message: string;
  meta?: Record<string, unknown>;
}

export interface DispenseFormPayload {
  medicine_code: string;
  patient_ref: string;
  quantity: number;
  dispensed_at: string;
  authorisation_ref: string;
  idempotency_key: string;
}

