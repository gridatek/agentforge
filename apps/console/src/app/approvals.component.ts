import { Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription, switchMap, timer } from 'rxjs';
import { AgentService, PendingApprovalItem } from './agent.service';

@Component({
  selector: 'app-approvals',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="ops-head">
      <h2>Approval queue</h2>
      <span class="muted" *ngIf="!error">live · refreshes every 5s</span>
    </div>

    <div class="pii" *ngIf="error">⚠️ {{ error }}</div>

    <div class="card empty" *ngIf="!error && !items.length">
      Nothing waiting. Sensitive actions (e.g. filing a SAR) pause here for sign-off.
    </div>

    <div class="card approval" *ngFor="let item of items">
      <div class="muted">{{ item.thread_id }} · {{ item.created_at * 1000 | date: 'short' }}</div>
      <p class="q">“{{ item.question }}”</p>
      <p>The agent wants to run <code>{{ item.action.name }}</code>:</p>
      <pre>{{ item.action.args | json }}</pre>
      <div class="row">
        <button (click)="decide(item, 'approve')" [disabled]="busy.has(item.thread_id)">
          Approve
        </button>
        <button
          class="secondary"
          (click)="decide(item, 'reject')"
          [disabled]="busy.has(item.thread_id)"
        >
          Reject
        </button>
      </div>
    </div>
  `,
  styles: [
    `
      .ops-head {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
      }
      .muted {
        font-size: 0.8rem;
        color: #718096;
      }
      .q {
        font-style: italic;
        color: #2d3748;
      }
      .card.empty {
        color: #718096;
      }
    `,
  ],
})
export class ApprovalsComponent implements OnInit, OnDestroy {
  items: PendingApprovalItem[] = [];
  error = '';
  busy = new Set<string>();
  private sub?: Subscription;

  constructor(private agent: AgentService) {}

  ngOnInit(): void {
    this.sub = timer(0, 5000)
      .pipe(switchMap(() => this.agent.approvals()))
      .subscribe({
        next: (items) => {
          this.error = '';
          // Don't yank a row out from under an in-flight decision.
          this.items = items.filter((i) => !this.busy.has(i.thread_id));
        },
        error: (e) => (this.error = `Couldn't load the queue: ${e?.message ?? e}`),
      });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  decide(item: PendingApprovalItem, decision: 'approve' | 'reject'): void {
    this.busy.add(item.thread_id);
    this.agent.approve(item.thread_id, decision).subscribe({
      next: () => {
        this.busy.delete(item.thread_id);
        this.items = this.items.filter((i) => i.thread_id !== item.thread_id);
      },
      error: (e) => {
        this.busy.delete(item.thread_id);
        this.error = `Decision failed: ${e?.message ?? e}`;
      },
    });
  }
}
