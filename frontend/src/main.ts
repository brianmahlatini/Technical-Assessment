/*
 * Angular bootstrap file.
 *
 * Why this file exists:
 *   This is the frontend entry point loaded by the browser. It starts the root
 *   application component and registers the shared providers that every view
 *   needs: HTTP for API calls and Router for page navigation.
 */

import { provideHttpClient } from '@angular/common/http';
import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';

import { AppComponent } from './app/app.component';
import { routes } from './app/app.routes';

bootstrapApplication(AppComponent, {
  // Providers are declared at bootstrap level so standalone page components can
  // stay focused on their view logic instead of repeating infrastructure setup.
  providers: [provideHttpClient(), provideRouter(routes)]
});

