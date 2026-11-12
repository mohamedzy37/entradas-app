/**
 * URL base de la API.
 *
 * En desarrollo se usa el proxy de Vite (`/api` -> http://localhost:3000), asi
 * que no hay CORS ni peticiones cross-site. Se puede sobreescribir con
 * VITE_API_URL para apuntar a otro backend.
 */
export const BASE_URL: string = import.meta.env.VITE_API_URL ?? '/api';
