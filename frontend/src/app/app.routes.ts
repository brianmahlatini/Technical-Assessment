import { Routes } from '@angular/router';

import { DispenseCaptureComponent } from './pages/dispense-capture/dispense-capture.component';
import { MedicineDetailComponent } from './pages/medicine-detail/medicine-detail.component';
import { MedicineSearchComponent } from './pages/medicine-search/medicine-search.component';
import { PatientLedgerComponent } from './pages/patient-ledger/patient-ledger.component';

export const routes: Routes = [
  { path: '', component: MedicineSearchComponent },
  { path: 'medicines/:code', component: MedicineDetailComponent },
  { path: 'dispense', component: DispenseCaptureComponent },
  { path: 'ledger', component: PatientLedgerComponent }
];

