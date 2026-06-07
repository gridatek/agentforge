// Base URL of the AgentForge API gateway. In docker-compose both the console
// and the API are reachable on localhost. Override per environment via Angular
// fileReplacements if you deploy them on different hosts.
export const environment = {
  apiBase: 'http://localhost:8000',
};
