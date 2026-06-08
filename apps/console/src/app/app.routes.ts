import { Routes } from '@angular/router';
import { ChatComponent } from './chat.component';
import { MetricsComponent } from './metrics.component';

export const routes: Routes = [
  { path: '', component: ChatComponent, title: 'AgentForge — Chat' },
  { path: 'ops', component: MetricsComponent, title: 'AgentForge — Operations' },
  { path: '**', redirectTo: '' },
];
