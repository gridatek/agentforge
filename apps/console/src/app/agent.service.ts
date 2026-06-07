import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

// Point at the FastAPI gateway. In docker-compose both run on localhost.
const API_BASE = 'http://localhost:8000';

export interface PendingAction {
  id?: string;
  name: string;
  args: Record<string, unknown>;
}

export interface ChatResponse {
  thread_id: string;
  answer?: string;
  citations: { source: string; title: string; snippet: string; score: number }[];
  pii_found: string[];
  approval_required: boolean;
  pending_action?: PendingAction;
}

@Injectable({ providedIn: 'root' })
export class AgentService {
  constructor(private http: HttpClient) {}

  chat(message: string, threadId?: string): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${API_BASE}/chat`, { message, thread_id: threadId });
  }

  approve(threadId: string, decision: 'approve' | 'reject'): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${API_BASE}/approve`, {
      thread_id: threadId,
      decision,
    });
  }
}
