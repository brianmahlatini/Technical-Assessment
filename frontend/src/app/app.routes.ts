/*
 * Frontend route table.
 *
 * Why this file exists:
 *   Navigation is kept separate from components so reviewers can see the four
 *   required assessment views in one place and add future pages without editing
 *   the root shell.
 */

import { Routes } from '@angular/router';

import { DispenseCaptureComponent } from './pages/dispense-capture/dispense-capture.component';
import { MedicineDetailComponent } from './pages/medicine-detail/medicine-detail.component';
import { MedicineSearchComponent } from './pages/medicine-search/medicine-search.component';
import { PatientLedgerComponent } from './pages/patient-ledger/patient-ledger.component';

export const routes: Routes = [
  // Default route opens the searchable medicine catalogue.
  { path: '', component: MedicineSearchComponent },

  // Medicine code is part of the URL so detail pages can be shared/bookmarked.
  { path: 'medicines/:code', component: MedicineDetailComponent },

  // Capture is separate from search/detail because it has its own form state.
  { path: 'dispense', component: DispenseCaptureComponent },

  // Ledger is separate so patient history lookup remains focused and simple.
  { path: 'ledger', component: PatientLedgerComponent }
];

