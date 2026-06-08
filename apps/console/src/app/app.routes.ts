import { Routes } from '@angular/router';
import { ApprovalsComponent } from './approvals.component';
import { ChatComponent } from './chat.component';
import { MetricsComponent } from './metrics.component';

export const routes: Routes = [
  { path: '', component: ChatComponent, title: 'AgentForge — Chat' },
  { path: 'approvals', component: ApprovalsComponent, title: 'AgentForge — Approvals' },
  { path: 'ops', component: MetricsComponent, title: 'AgentForge — Operations' },
  { path: '**', redirectTo: '' },
];
