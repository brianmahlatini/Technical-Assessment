import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

@Component({
  standalone: true,
  selector: 'app-root',
  imports: [CommonModule, RouterLink, RouterOutlet],
  template: `
    <header class="topbar">
      <a routerLink="/" class="brand">EMGuidance Formulary</a>
      <nav>
        <a routerLink="/">Medicines</a>
        <a routerLink="/dispense">Capture</a>
        <a routerLink="/ledger">Ledger</a>
      </nav>
    </header>
    <main>
      <router-outlet></router-outlet>
    </main>
  `
})
export class AppComponent {}

