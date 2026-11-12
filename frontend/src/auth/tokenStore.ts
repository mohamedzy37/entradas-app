/**
 * Gestion de tokens en el navegador.
 *
 * Requisito del enunciado: la sesion NO se almacena en el backend. Toda la
 * sesion vive en el cliente:
 *
 *  - ACCESS token: JWT de vida corta (15 min) que se guarda SOLO en memoria
 *    (una variable de este modulo). No esta en localStorage ni en cookies, asi
 *    que un script inyectado no puede leerlo de ningun almacen persistente.
 *    Se pierde al recargar y se recupera llamando a /auth/refresh.
 *  - REFRESH token: JWT de vida larga (7 dias) en una cookie HttpOnly,
 *    Secure y SameSite=Strict que pone el servidor. JavaScript NO puede
 *    leerlo: este modulo nunca lo ve. El navegador lo adjunta solo en las
 *    peticiones a /api/auth.
 *  - En localStorage solo se guarda una marca sin valor secreto ("hay sesion")
 *    para no llamar a /auth/refresh en cada visita anonima.
 *  - Las peticiones concurrentes que necesitan refrescar comparten una unica
 *    llamada (single flight).
 */

import { BASE_URL } from '../api/base';
import type { AuthSession } from '../api/types';

const SESSION_HINT_KEY = 'entradas:has-session';

/** Access token en memoria: nunca se persiste. */
let accessToken: string | null = null;
/** Momento (epoch ms) en que caduca el access token actual. */
let accessExpiresAt = 0;

/** Unica promesa de refresco en vuelo (single flight). */
let refreshPromise: Promise<AuthSession | null> | null = null;

/** Callback de sesion caducada, registrado por AuthContext. */
let onSessionExpired: (() => void) | null = null;

// Limpieza de la version anterior, que guardaba el refresh en localStorage.
try {
  window.localStorage.removeItem('entradas:refresh-token');
  window.localStorage.removeItem('entradas:device-id');
} catch {
  /* sin almacenamiento */
}

function setSessionHint(active: boolean): void {
  try {
    if (active) window.localStorage.setItem(SESSION_HINT_KEY, '1');
    else window.localStorage.removeItem(SESSION_HINT_KEY);
  } catch {
    /* almacenamiento no disponible (modo privado, etc.) */
  }
}

/** true si probablemente hay una cookie de refresh (no se puede leer: es HttpOnly). */
export function hasStoredSession(): boolean {
  try {
    return window.localStorage.getItem(SESSION_HINT_KEY) === '1';
  } catch {
    return false;
  }
}

export function setSessionExpiredHandler(handler: (() => void) | null): void {
  onSessionExpired = handler;
}

/** Guarda la sesion recibida del servidor (login, registro o refresh). */
export function setSession(session: AuthSession): void {
  accessToken = session.accessToken;
  // Se renueva 15 s antes de que caduque para no enviar un token a punto de expirar.
  accessExpiresAt = Date.now() + Math.max(session.expiresIn - 15, 1) * 1000;
  setSessionHint(true);
}

/** Devuelve el access token en memoria si aun es valido. */
export function getAccessToken(): string | null {
  if (!accessToken) return null;
  if (Date.now() >= accessExpiresAt) return null;
  return accessToken;
}

/** Borra la sesion del cliente (la cookie la borra el servidor en /logout). */
export function clearSession(): void {
  accessToken = null;
  accessExpiresAt = 0;
  setSessionHint(false);
}

/** Notifica a la app que la sesion ha dejado de ser valida. */
export function notifySessionExpired(): void {
  clearSession();
  onSessionExpired?.();
}

async function performRefresh(): Promise<AuthSession | null> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      // Envia la cookie HttpOnly del refresh (tambien si la API esta en otro origen).
      credentials: 'include',
    });
  } catch {
    // Fallo de red: no se cierra la sesion, se reintentara mas tarde.
    return null;
  }

  if (!response.ok) {
    // Refresh caducado, revocado o inexistente: cerrar sesion en el cliente.
    notifySessionExpired();
    return null;
  }

  const body = (await response.json()) as { data: AuthSession };
  setSession(body.data);
  return body.data;
}

/**
 * Devuelve un access token valido, refrescando si es necesario.
 * Devuelve null si no hay sesion o si el refresh ya no es valido.
 */
export async function ensureAccessToken(options: { force?: boolean } = {}): Promise<string | null> {
  const current = options.force ? null : getAccessToken();
  if (current) return current;

  if (!hasStoredSession()) return null;

  // Single flight: si ya hay un refresco en curso, se reutiliza.
  if (!refreshPromise) {
    refreshPromise = performRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  const session = await refreshPromise;
  return session?.accessToken ?? getAccessToken();
}

/** Cierra la sesion: el servidor borra la cookie y el cliente olvida el access. */
export async function revokeSession(): Promise<void> {
  clearSession();
  try {
    await fetch(`${BASE_URL}/auth/logout`, { method: 'POST', credentials: 'include' });
  } catch {
    /* si falla, el refresh caducara igualmente */
  }
}
