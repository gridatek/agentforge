// The console calls the API same-origin under /api — nginx (prod) or the Angular
// dev-server proxy (local `npm start`) forwards /api/* to the gateway. This keeps
// one console image working in any environment with no build-time host baked in.
export const environment = {
  apiBase: '/api',
};
