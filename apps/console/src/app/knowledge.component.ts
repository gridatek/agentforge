import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AgentService, DocumentSummaryItem } from './agent.service';

@Component({
  selector: 'app-knowledge',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="ops-head">
      <h2>Knowledge base</h2>
      <span class="muted" *ngIf="!error && docs.length">
        {{ docs.length }} sources · {{ totalChunks }} chunks
      </span>
    </div>

    <div class="pii" *ngIf="error">⚠️ {{ error }}</div>

    <div class="card empty" *ngIf="loaded && !error && !docs.length">
      Nothing ingested yet. Run the ingest job (or boot with auto-ingest) to load
      the corpus the agent retrieves from.
    </div>

    <table class="docs" *ngIf="docs.length">
      <thead>
        <tr>
          <th>Source</th>
          <th>Title</th>
          <th class="num">Chunks</th>
        </tr>
      </thead>
      <tbody>
        <tr *ngFor="let d of docs">
          <td><code>{{ d.source }}</code></td>
          <td>{{ d.title || '—' }}</td>
          <td class="num">{{ d.chunks }}</td>
        </tr>
      </tbody>
    </table>
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
      table.docs {
        width: 100%;
        border-collapse: collapse;
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        overflow: hidden;
        margin-top: 12px;
      }
      .docs th,
      .docs td {
        text-align: left;
        padding: 10px 12px;
        border-bottom: 1px solid #edf2f7;
        font-size: 0.9rem;
      }
      .docs th {
        background: #f7fafc;
        color: #4a5568;
        font-weight: 600;
      }
      .docs .num {
        text-align: right;
      }
      .docs tr:last-child td {
        border-bottom: 0;
      }
    `,
  ],
})
export class KnowledgeComponent implements OnInit {
  docs: DocumentSummaryItem[] = [];
  loaded = false;
  error = '';

  constructor(private agent: AgentService) {}

  get totalChunks(): number {
    return this.docs.reduce((acc, d) => acc + d.chunks, 0);
  }

  ngOnInit(): void {
    this.agent.documents().subscribe({
      next: (docs) => {
        this.docs = docs;
        this.loaded = true;
      },
      error: (e) => {
        this.error = `Couldn't load the knowledge base: ${e?.message ?? e}`;
        this.loaded = true;
      },
    });
  }
}
