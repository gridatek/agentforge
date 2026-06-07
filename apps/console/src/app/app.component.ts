import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AgentService, ChatResponse } from './agent.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="container">
      <h1>🛠️ AgentForge — Compliance Assistant</h1>

      <div class="row">
        <input
          type="text"
          [(ngModel)]="message"
          (keyup.enter)="send()"
          placeholder="Ask a compliance question…"
        />
        <button (click)="send()" [disabled]="loading">
          {{ loading ? '…' : 'Send' }}
        </button>
      </div>

      <div class="card" *ngIf="response as r">
        <div class="pii" *ngIf="r.pii_found.length">
          PII redacted before processing: {{ r.pii_found.join(', ') }}
        </div>

        <!-- Approval queue: a sensitive action is awaiting human sign-off -->
        <div class="approval" *ngIf="r.approval_required && r.pending_action as a">
          <strong>Approval required</strong>
          <p>The agent wants to run <code>{{ a.name }}</code>:</p>
          <pre>{{ a.args | json }}</pre>
          <div class="row">
            <button (click)="decide('approve')">Approve</button>
            <button class="secondary" (click)="decide('reject')">Reject</button>
          </div>
        </div>

        <!-- Normal answer + citations -->
        <ng-container *ngIf="!r.approval_required">
          <p>{{ r.answer }}</p>
          <div class="citation" *ngFor="let c of r.citations">
            [{{ c.source }}] {{ c.snippet }}
          </div>
        </ng-container>
      </div>
    </div>
  `,
})
export class AppComponent {
  message = '';
  loading = false;
  response: ChatResponse | null = null;
  private threadId?: string;

  constructor(private agent: AgentService) {}

  send(): void {
    if (!this.message.trim()) return;
    this.loading = true;
    this.agent.chat(this.message, this.threadId).subscribe({
      next: (r) => {
        this.response = r;
        this.threadId = r.thread_id;
        this.loading = false;
      },
      error: () => (this.loading = false),
    });
  }

  decide(decision: 'approve' | 'reject'): void {
    if (!this.threadId) return;
    this.loading = true;
    this.agent.approve(this.threadId, decision).subscribe({
      next: (r) => {
        this.response = r;
        this.loading = false;
      },
      error: () => (this.loading = false),
    });
  }
}
