import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AgentService, EvalReport } from './agent.service';

@Component({
  selector: 'app-evals',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="ops-head">
      <h2>Evals</h2>
      <span class="muted" *ngIf="report">
        {{ report.generated_at | date: 'medium' }}
      </span>
    </div>

    <div class="pii" *ngIf="error">⚠️ {{ error }}</div>

    <div class="card empty" *ngIf="loaded && !error && !report">
      No eval report in this environment yet. Run the suite against a live stack:
      <pre>python evals/run_evals.py --out evals/results.json</pre>
      (CI runs this as a gate and uploads the report as a build artifact.)
    </div>

    <ng-container *ngIf="report as r">
      <div class="tiles">
        <div class="tile" [class.bad]="r.pass_rate < r.threshold">
          <div class="tile-value">{{ r.pass_rate * 100 | number: '1.0-0' }}%</div>
          <div class="tile-label">Pass rate</div>
          <div class="tile-hint">threshold {{ r.threshold * 100 | number: '1.0-0' }}%</div>
        </div>
        <div class="tile">
          <div class="tile-value">{{ r.passed }} / {{ r.total }}</div>
          <div class="tile-label">Cases passing</div>
        </div>
        <div class="tile">
          <div class="tile-value">{{ r.pass_rate >= r.threshold ? 'PASS' : 'FAIL' }}</div>
          <div class="tile-label">Gate</div>
        </div>
      </div>

      <table class="docs">
        <thead>
          <tr>
            <th></th>
            <th>Case</th>
            <th>Question</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let c of r.cases">
            <td>{{ c.passed ? '✅' : '❌' }}</td>
            <td><code>{{ c.id }}</code></td>
            <td>{{ c.question }}</td>
            <td [class.fail]="!c.passed">{{ c.detail }}</td>
          </tr>
        </tbody>
      </table>
    </ng-container>
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
      .card.empty {
        color: #718096;
      }
      .tiles {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
        gap: 12px;
        margin: 12px 0;
      }
      .tile {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
      }
      .tile.bad {
        border-color: #e53e3e;
        background: #fff5f5;
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
      table.docs {
        width: 100%;
        border-collapse: collapse;
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        overflow: hidden;
      }
      .docs th,
      .docs td {
        text-align: left;
        padding: 10px 12px;
        border-bottom: 1px solid #edf2f7;
        font-size: 0.9rem;
        vertical-align: top;
      }
      .docs th {
        background: #f7fafc;
        color: #4a5568;
        font-weight: 600;
      }
      .docs td.fail {
        color: #c53030;
      }
      .docs tr:last-child td {
        border-bottom: 0;
      }
    `,
  ],
})
export class EvalsComponent implements OnInit {
  report: EvalReport | null = null;
  loaded = false;
  error = '';

  constructor(private agent: AgentService) {}

  ngOnInit(): void {
    this.agent.evals().subscribe({
      next: (report) => {
        this.report = report;
        this.loaded = true;
      },
      error: (e) => {
        this.error = `Couldn't load evals: ${e?.message ?? e}`;
        this.loaded = true;
      },
    });
  }
}
