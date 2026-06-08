import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="container">
      <header class="app-header">
        <h1>🛠️ AgentForge</h1>
        <nav>
          <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">
            Chat
          </a>
          <a routerLink="/ops" routerLinkActive="active">Operations</a>
        </nav>
      </header>

      <router-outlet />
    </div>
  `,
  styles: [
    `
      .app-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 16px;
      }
      nav {
        display: flex;
        gap: 16px;
      }
      nav a {
        text-decoration: none;
        color: #4a5568;
        padding: 8px 0;
        border-bottom: 2px solid transparent;
      }
      nav a.active {
        color: #2b6cb0;
        border-bottom-color: #2b6cb0;
      }
    `,
  ],
})
export class AppComponent {}
