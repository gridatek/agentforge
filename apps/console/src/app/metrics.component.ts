import { Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription, switchMap, timer } from 'rxjs';
import { AgentService } from './agent.service';
import { labelValues, parsePrometheus, Sample, sum, value } from './prometheus';

interface Stat {
  label: string;
  value: string;
  hint?: string;
}

@Component({
  selector: 'app-metrics',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="ops-head">
      <h2>Operations</h2>
      <span class="muted" *ngIf="!error">live · refreshes every 5s</span>
    </div>

    <div class="pii" *ngIf="error">⚠️ {{ error }}</div>

    <div class="tiles" *ngIf="!error">
      <div class="tile" *ngFor="let s of stats">
        <div class="tile-value">{{ s.value }}</div>
        <div class="tile-label">{{ s.label }}</div>
        <div class="tile-hint" *ngIf="s.hint">{{ s.hint }}</div>
      </div>
      <div class="tile empty" *ngIf="!stats.length">
        No metrics yet — ask a few questions in Chat, then come back.
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
      .tiles {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        gap: 12px;
        margin-top: 12px;
      }
      .tile {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
      }
      .tile.empty {
        grid-column: 1 / -1;
        color: #718096;
      }
      .tile-value {
        font-size: 1.8rem;
        font-weight: 600;
      }
      .tile-label {
        color: #2d3748;
        margin-top: 4px;
      }
      .tile-hint {
        font-size: 0.8rem;
        color: #718096;
        margin-top: 4px;
      }
    `,
  ],
})
export class MetricsComponent implements OnInit, OnDestroy {
  stats: Stat[] = [];
  error = '';
  private sub?: Subscription;

  constructor(private agent: AgentService) {}

  ngOnInit(): void {
    // Poll immediately, then every 5s.
    this.sub = timer(0, 5000)
      .pipe(switchMap(() => this.agent.metrics()))
      .subscribe({
        next: (text) => {
          this.error = '';
          this.stats = this.toStats(parsePrometheus(text));
        },
        error: (e) => (this.error = `Couldn't load metrics: ${e?.message ?? e}`),
      });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  private toStats(s: Sample[]): Stat[] {
    const chats = sum(s, 'agentforge_chat_requests_total');
    const grounded = value(s, 'agentforge_answers_total', { grounded: 'true' });
    const refusals = value(s, 'agentforge_answers_total', { grounded: 'false' });
    const answers = grounded + refusals;
    const approve = value(s, 'agentforge_approvals_total', { decision: 'approve' });
    const reject = value(s, 'agentforge_approvals_total', { decision: 'reject' });
    const pii = sum(s, 'agentforge_pii_redactions_total');
    const http = sum(s, 'agentforge_http_requests_total');

    // Nothing has been recorded yet — let the template show the empty state.
    if (chats + answers + approve + reject + pii + http === 0) return [];

    const groundedPct = answers ? Math.round((grounded / answers) * 100) : 0;
    const piiKinds = labelValues(s, 'agentforge_pii_redactions_total', 'label');

    return [
      { label: 'Chat requests', value: `${chats}` },
      {
        label: 'Grounded answers',
        value: `${groundedPct}%`,
        hint: `${grounded} grounded · ${refusals} refused`,
      },
      {
        label: 'Approvals',
        value: `${approve} / ${reject}`,
        hint: 'approved / rejected',
      },
      {
        label: 'PII redactions',
        value: `${pii}`,
        hint: piiKinds.length ? piiKinds.join(', ') : undefined,
      },
      { label: 'HTTP requests', value: `${http}` },
    ];
  }
}
