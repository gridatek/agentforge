import { Routes } from '@angular/router';
import { ApprovalsComponent } from './approvals.component';
import { ChatComponent } from './chat.component';
import { KnowledgeComponent } from './knowledge.component';
import { MetricsComponent } from './metrics.component';

export const routes: Routes = [
  { path: '', component: ChatComponent, title: 'AgentForge — Chat' },
  { path: 'approvals', component: ApprovalsComponent, title: 'AgentForge — Approvals' },
  { path: 'knowledge', component: KnowledgeComponent, title: 'AgentForge — Knowledge' },
  { path: 'ops', component: MetricsComponent, title: 'AgentForge — Operations' },
  { path: '**', redirectTo: '' },
];
