/*
 * Root application shell.
 *
 * Why this file exists:
 *   The root component owns layout shared by every frontend page: the top
 *   navigation and the router outlet. Feature views live in separate page
 *   components so the UI is not packed into one large file.
 */

import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

@Component({
  standalone: true,
  selector: 'app-root',
  imports: [CommonModule, RouterLink, RouterOutlet],
  template: `
    <!-- Shared navigation stays here so every route has the same app frame. -->
    <header class="topbar">
      <a routerLink="/" class="brand">EMGuidance Formulary</a>
      <nav>
        <a routerLink="/">Medicines</a>
        <a routerLink="/dispense">Capture</a>
        <a routerLink="/ledger">Ledger</a>
      </nav>
    </header>
    <!-- Routed pages render here: search, detail, dispense capture, and ledger. -->
    <main>
      <router-outlet></router-outlet>
    </main>
  `
})
export class AppComponent {}

