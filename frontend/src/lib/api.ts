// Backend API base. Empty string in dev/tests (same-origin / Vite proxy);
// set to the Container App FQDN at build time via VITE_API_BASE_URL in prod.
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export const apiUrl = (path: string) => `${API_BASE}${path}`
