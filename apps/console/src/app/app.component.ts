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
          [disabled]="streaming"
          placeholder="Ask a compliance question…"
        />
        <button (click)="send()" [disabled]="streaming || !message.trim()">
          {{ streaming ? '…' : 'Send' }}
        </button>
      </div>

      <div class="pii" *ngIf="error">⚠️ {{ error }}</div>

      <div class="card" *ngIf="response as r">
        <div class="pii" *ngIf="r.pii_found.length">
          PII redacted before processing: {{ r.pii_found.join(', ') }}
        </div>

        <!-- A sensitive action is awaiting human sign-off -->
        <div class="approval" *ngIf="r.approval_required && r.pending_action as a">
          <strong>Approval required</strong>
          <p>The agent wants to run <code>{{ a.name }}</code>:</p>
          <pre>{{ a.args | json }}</pre>
          <div class="row">
            <button (click)="decide('approve')" [disabled]="streaming">Approve</button>
            <button class="secondary" (click)="decide('reject')" [disabled]="streaming">
              Reject
            </button>
          </div>
        </div>

        <!-- Streamed answer + citations -->
        <ng-container *ngIf="!r.approval_required">
          <p>{{ r.answer }}<span *ngIf="streaming" class="cursor">▌</span></p>
          <div class="citation" *ngFor="let c of r.citations">[{{ c.source }}] {{ c.snippet }}</div>
        </ng-container>
      </div>
    </div>
  `,
  styles: [
    `
      .cursor {
        animation: blink 1s steps(2, start) infinite;
      }
      @keyframes blink {
        to {
          visibility: hidden;
        }
      }
    `,
  ],
})
export class AppComponent {
  message = '';
  streaming = false;
  error = '';
  response: ChatResponse | null = null;
  private threadId?: string;

  constructor(private agent: AgentService) {}

  send(): void {
    const text = this.message.trim();
    if (!text || this.streaming) return;

    this.streaming = true;
    this.error = '';
    this.response = {
      thread_id: this.threadId ?? '',
      answer: '',
      citations: [],
      pii_found: [],
      approval_required: false,
    };
    this.message = '';
    let accumulated = '';

    this.agent.streamChat(text, this.threadId).subscribe({
      next: (ev) => {
        if (!this.response) return;
        switch (ev.type) {
          case 'thread':
            this.threadId = ev.threadId;
            this.response.thread_id = ev.threadId;
            break;
          case 'token':
            accumulated += ev.text;
            this.response.answer = accumulated;
            break;
          case 'approval_required':
            this.response.approval_required = true;
            this.response.pending_action = ev.action;
            break;
          case 'done':
            this.response.answer = ev.answer || accumulated;
            this.response.citations = ev.citations;
            this.response.pii_found = ev.piiFound;
            break;
          case 'error':
            this.error = ev.message;
            break;
        }
      },
      complete: () => (this.streaming = false),
    });
  }

  decide(decision: 'approve' | 'reject'): void {
    if (!this.threadId || this.streaming) return;
    this.streaming = true;
    this.error = '';
    this.agent.approve(this.threadId, decision).subscribe({
      next: (r) => {
        this.response = r;
        this.streaming = false;
      },
      error: (e) => {
        this.error = `Approval failed: ${e?.message ?? e}`;
        this.streaming = false;
      },
    });
  }
}
