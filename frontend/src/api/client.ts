import {
  clearSession,
  ensureAccessToken,
  hasStoredSession,
  revokeSession,
  setSession,
} from '../auth/tokenStore';
import { BASE_URL } from './base';
import type {
  AdminStats,
  AuthSession,
  Category,
  DataResponse,
  EventDetail,
  EventStatus,
  EventSummary,
  EventType,
  ListResponse,
  Order,
  OrderStatus,
  Payment,
  Role,
  TicketLookup,
  User,
  Venue,
} from './types';

export { ApiError, type ApiError as ApiErrorType } from './error';
import { ApiError } from './error';

type QueryValue = string | number | boolean | undefined | null;

function toQueryString(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

interface RequestOptions extends RequestInit {
  /** Evita el intento automatico de refrescar el token (para /auth/refresh). */
  skipAuthRetry?: boolean;
  /** No adjunta el access token aunque exista. */
  anonymous?: boolean;
}

async function rawRequest(path: string, options: RequestOptions = {}): Promise<Response> {
  const { skipAuthRetry: _skip, anonymous, headers, ...init } = options;

  const finalHeaders = new Headers(headers);
  if (init.body && !finalHeaders.has('Content-Type')) {
    finalHeaders.set('Content-Type', 'application/json');
  }

  if (!anonymous) {
    const token = await ensureAccessToken();
    if (token) finalHeaders.set('Authorization', `Bearer ${token}`);
  }

  try {
    return await fetch(`${BASE_URL}${path}`, {
      // El access token viaja en la cabecera Authorization. La cookie HttpOnly
      // del refresh solo se necesita en /auth (login, registro, refresh, logout).
      credentials: path.startsWith('/auth/') ? 'include' : 'omit',
      ...init,
      headers: finalHeaders,
    });
  } catch {
    throw new ApiError(
      0,
      'NETWORK_ERROR',
      'No se pudo conectar con el servidor. \u00bfEst\u00e1 la API en marcha?',
    );
  }
}

async function parse<T>(response: Response): Promise<T> {
  if (response.status === 204) return null as T;

  const text = await response.text();
  const body = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const apiError = body?.error;
    throw new ApiError(
      response.status,
      apiError?.code ?? 'ERROR',
      apiError?.message ?? `Error ${response.status}`,
      apiError?.details,
    );
  }

  return body as T;
}

/**
 * Peticion autenticada con reintento unico:
 * si el servidor responde 401 (access token caducado o revocado), se fuerza un
 * refresco y se repite una sola vez. Si vuelve a fallar, se cierra la sesion.
 */
async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await rawRequest(path, options);

  if (response.status === 401 && !options.skipAuthRetry && !options.anonymous) {
    const token = await ensureAccessToken({ force: true });
    if (token) {
      response = await rawRequest(path, { ...options, skipAuthRetry: true });
    }
  }

  return parse<T>(response);
}

function sessionRequest(path: string, payload: unknown): Promise<DataResponse<AuthSession>> {
  return request<DataResponse<AuthSession>>(path, {
    method: 'POST',
    body: payload === undefined ? undefined : JSON.stringify(payload),
    anonymous: true,
    skipAuthRetry: true,
  }).then((response) => {
    setSession(response.data);
    return response;
  });
}

export interface CreateOrderPayload {
  buyer: { name: string; email: string; phone?: string };
  items: Array<{ ticketTypeId: string; quantity: number }>;
}

export interface PayPayload {
  cardNumber: string;
  cardHolder: string;
  expiryMonth: number;
  expiryYear: number;
  cvv: string;
}

export interface RegisterPayload {
  name: string;
  email: string;
  password: string;
  phone?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface EventInput {
  title: string;
  description?: string | null;
  type: EventType;
  status?: EventStatus;
  imageUrl?: string | null;
  startAt: string;
  endAt?: string | null;
  doorsOpenAt?: string | null;
  categoryId?: string | null;
  venueId: string;
}

export interface TicketTypeInput {
  name: string;
  description?: string | null;
  priceCents: number;
  currency?: string;
  quantityTotal: number;
  maxPerOrder?: number;
  isActive?: boolean;
}

export interface VenueInput {
  name: string;
  address: string;
  city: string;
  country?: string;
  capacity?: number | null;
  latitude?: number | null;
  longitude?: number | null;
}

export const api = {
  // --- Autenticacion (access JWT en cabecera, refresh JWT en cookie HttpOnly) ---
  register: (payload: RegisterPayload) => sessionRequest('/auth/register', payload),

  login: (payload: LoginPayload) => sessionRequest('/auth/login', payload),

  /** Renueva el access token usando la cookie HttpOnly (el refresh tambien rota). */
  refresh: () => sessionRequest('/auth/refresh', undefined),

  logout: () => revokeSession(),

  me: () => request<DataResponse<{ user: User }>>('/auth/me'),

  /** true si probablemente hay una sesion recuperable (cookie de refresh). */
  hasSession: () => hasStoredSession(),

  // --- Catalogo publico ---
  listMyOrders: () => request<DataResponse<Order[]>>('/orders'),

  listEvents: (params: Record<string, QueryValue> = {}) =>
    request<ListResponse<EventSummary>>(`/events${toQueryString(params)}`),

  getEvent: (idOrSlug: string) => request<DataResponse<EventDetail>>(`/events/${idOrSlug}`),

  listCategories: () => request<DataResponse<Category[]>>('/categories'),

  listVenues: (params: Record<string, QueryValue> = {}) =>
    request<ListResponse<Venue>>(`/venues${toQueryString({ limit: 100, ...params })}`),

  // --- Pedidos ---
  createOrder: (payload: CreateOrderPayload) =>
    request<DataResponse<Order>>('/orders', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getOrder: (reference: string) => request<DataResponse<Order>>(`/orders/${reference}`),

  payOrder: (reference: string, payload: PayPayload) =>
    request<{ approved: boolean; data: { order: Order; payment: Payment } }>(
      `/orders/${reference}/pay`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),

  cancelOrder: (reference: string) =>
    request<DataResponse<Order>>(`/orders/${reference}/cancel`, { method: 'POST' }),

  // --- Entradas ---
  getTicket: (code: string) => request<DataResponse<TicketLookup>>(`/tickets/${code}`),

  checkInTicket: (code: string) =>
    request<DataResponse<TicketLookup>>(`/tickets/${code}/check-in`, { method: 'POST' }),

  // --- Panel de gestion (MANAGER/ADMIN) ---
  adminStats: () => request<DataResponse<AdminStats>>('/admin/stats'),

  adminOrders: (params: Record<string, QueryValue> = {}) =>
    request<ListResponse<Order>>(`/admin/orders${toQueryString(params)}`),

  adminCreateEvent: (payload: EventInput) =>
    request<DataResponse<EventDetail>>('/admin/events', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  adminUpdateEvent: (eventId: string, payload: Partial<EventInput>) =>
    request<DataResponse<EventDetail>>(`/admin/events/${eventId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  adminDeleteEvent: (eventId: string) =>
    request<null>(`/admin/events/${eventId}`, { method: 'DELETE' }),

  adminCreateTicketType: (eventId: string, payload: TicketTypeInput) =>
    request<DataResponse<EventDetail>>(`/admin/events/${eventId}/ticket-types`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  adminUpdateTicketType: (ticketTypeId: string, payload: Partial<TicketTypeInput>) =>
    request<DataResponse<EventDetail>>(`/admin/ticket-types/${ticketTypeId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  adminDeleteTicketType: (ticketTypeId: string) =>
    request<null>(`/admin/ticket-types/${ticketTypeId}`, { method: 'DELETE' }),

  adminCreateVenue: (payload: VenueInput) =>
    request<DataResponse<Venue>>('/admin/venues', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // --- Panel de administracion (solo ADMIN) ---
  adminUsers: (params: Record<string, QueryValue> = {}) =>
    request<ListResponse<User>>(`/admin/users${toQueryString(params)}`),

  adminUpdateRole: (userId: string, role: Role) =>
    request<DataResponse<User>>(`/admin/users/${userId}/role`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    }),

  adminUpdateActive: (userId: string, isActive: boolean) =>
    request<DataResponse<User>>(`/admin/users/${userId}/active`, {
      method: 'PATCH',
      body: JSON.stringify({ isActive }),
    }),

  /** Invalida la sesion en todos los dispositivos del usuario. */
  logoutAll: () =>
    request<null>('/auth/logout-all', { method: 'POST' }).finally(() => clearSession()),

  /** Alias tipado del estado de pedido usado por el panel. */
  adminStatsByStatus: (status: OrderStatus) =>
    request<ListResponse<Order>>(`/admin/orders${toQueryString({ status })}`),
};
