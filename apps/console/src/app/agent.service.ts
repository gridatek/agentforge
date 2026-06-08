import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../environments/environment';

const API_BASE = environment.apiBase;

export interface PendingAction {
  id?: string;
  name: string;
  args: Record<string, unknown>;
}

export interface Citation {
  source: string;
  title: string;
  snippet: string;
  score: number;
}

export interface ChatResponse {
  thread_id: string;
  answer?: string;
  citations: Citation[];
  pii_found: string[];
  approval_required: boolean;
  pending_action?: PendingAction;
}

export interface PendingApprovalItem {
  thread_id: string;
  question: string;
  created_at: number;
  action: PendingAction;
}

export interface DocumentSummaryItem {
  source: string;
  title: string;
  chunks: number;
}

export type StreamEvent =
  | { type: 'thread'; threadId: string }
  | { type: 'token'; text: string }
  | { type: 'approval_required'; action: PendingAction }
  | { type: 'done'; answer: string; citations: Citation[]; piiFound: string[] }
  | { type: 'error'; message: string };

@Injectable({ providedIn: 'root' })
export class AgentService {
  constructor(private http: HttpClient) {}

  /** Non-streaming chat (kept as a simple fallback). */
  chat(message: string, threadId?: string): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${API_BASE}/chat`, { message, thread_id: threadId });
  }

  /** Resume a paused run after a human approves/rejects a sensitive action. */
  approve(threadId: string, decision: 'approve' | 'reject'): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${API_BASE}/approve`, {
      thread_id: threadId,
      decision,
    });
  }

  /** Raw Prometheus exposition text from the API's /metrics endpoint. */
  metrics(): Observable<string> {
    return this.http.get(`${API_BASE}/metrics`, { responseType: 'text' });
  }

  /** Runs currently paused awaiting human approval. */
  approvals(): Observable<PendingApprovalItem[]> {
    return this.http.get<PendingApprovalItem[]>(`${API_BASE}/approvals`);
  }

  /** Source documents ingested into the vector store. */
  documents(): Observable<DocumentSummaryItem[]> {
    return this.http.get<DocumentSummaryItem[]>(`${API_BASE}/documents`);
  }

  /**
   * Stream a chat response over SSE. Uses fetch (not EventSource) because the
   * endpoint is a POST. Emits typed events; unsubscribing aborts the request.
   */
  streamChat(message: string, threadId?: string): Observable<StreamEvent> {
    return new Observable<StreamEvent>((subscriber) => {
      const controller = new AbortController();

      (async () => {
        let response: Response;
        try {
          response = await fetch(`${API_BASE}/chat/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, thread_id: threadId ?? null }),
            signal: controller.signal,
          });
        } catch (err) {
          if (!controller.signal.aborted) {
            subscriber.next({ type: 'error', message: `Network error: ${err}` });
          }
          subscriber.complete();
          return;
        }

        if (!response.ok || !response.body) {
          subscriber.next({ type: 'error', message: `HTTP ${response.status}` });
          subscriber.complete();
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        try {
          for (;;) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            // SSE events are separated by a blank line.
            let sep: number;
            while ((sep = buffer.search(/\r?\n\r?\n/)) >= 0) {
              const rawEvent = buffer.slice(0, sep);
              buffer = buffer.slice(sep + (buffer[sep] === '\r' ? 4 : 2));
              const parsed = parseSse(rawEvent);
              if (parsed) subscriber.next(parsed);
            }
          }
        } catch (err) {
          if (!controller.signal.aborted) {
            subscriber.next({ type: 'error', message: `Stream error: ${err}` });
          }
        }
        subscriber.complete();
      })();

      return () => controller.abort();
    });
  }
}

/** Parse one raw SSE event block ("event: x\ndata: y") into a typed StreamEvent. */
function parseSse(raw: string): StreamEvent | null {
  let event = 'message';
  const dataLines: string[] = [];
  for (const line of raw.split(/\r?\n/)) {
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''));
  }
  const data = dataLines.join('\n');

  switch (event) {
    case 'thread':
      return { type: 'thread', threadId: data };
    case 'token':
      return { type: 'token', text: data };
    case 'approval_required':
      return { type: 'approval_required', action: JSON.parse(data) as PendingAction };
    case 'done': {
      const payload = JSON.parse(data) as {
        answer: string;
        citations: Citation[];
        pii_found: string[];
      };
      return {
        type: 'done',
        answer: payload.answer,
        citations: payload.citations ?? [],
        piiFound: payload.pii_found ?? [],
      };
    }
    default:
      return null;
  }
}
