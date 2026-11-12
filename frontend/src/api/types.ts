export type EventType =
  | 'MUSEUM'
  | 'FOOTBALL'
  | 'CINEMA'
  | 'FESTIVAL'
  | 'CONCERT'
  | 'THEATER'
  | 'OTHER';

export type EventStatus = 'DRAFT' | 'PUBLISHED' | 'SOLD_OUT' | 'CANCELLED' | 'FINISHED';

export type OrderStatus = 'PENDING' | 'PAID' | 'CANCELLED' | 'REFUNDED' | 'EXPIRED';
export type TicketStatus = 'VALID' | 'USED' | 'CANCELLED';
export type PaymentStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'REFUNDED';

/** Roles del sistema. El backend comprueba siempre el rol guardado en base de datos. */
export type Role = 'ADMIN' | 'MANAGER' | 'CLIENT';

export interface Category {
  id: string;
  name: string;
  slug: string;
  eventCount: number;
}

export interface Venue {
  id: string;
  name: string;
  address: string;
  city: string;
  country: string;
  capacity?: number | null;
  latitude?: number | null;
  longitude?: number | null;
}

export interface TicketType {
  id: string;
  name: string;
  description?: string | null;
  priceCents: number;
  price: string;
  currency: string;
  quantityTotal: number;
  quantitySold: number;
  available: number;
  soldOut: boolean;
  maxPerOrder: number;
  isActive?: boolean;
}

export interface EventSummary {
  id: string;
  title: string;
  slug: string;
  description?: string | null;
  type: EventType;
  status: string;
  imageUrl?: string | null;
  startAt: string;
  endAt?: string | null;
  doorsOpenAt?: string | null;
  currency: string;
  minPriceCents?: number | null;
  minPrice?: string | null;
  category?: Category | null;
  venue: Venue;
  isSoldOut: boolean;
}

export interface EventDetail extends EventSummary {
  ticketTypes: TicketType[];
}

export interface OrderItem {
  id: string;
  ticketTypeId: string;
  ticketTypeName: string;
  eventId: string;
  eventTitle: string;
  eventStartAt: string;
  quantity: number;
  unitPriceCents: number;
  unitPrice: string;
  subtotalCents: number;
  subtotal: string;
}

export interface Ticket {
  id: string;
  code: string;
  status: TicketStatus;
  holderName?: string | null;
  usedAt?: string | null;
  eventId: string;
  eventTitle: string;
  eventStartAt: string;
  ticketTypeName: string;
  createdAt: string;
}

export interface Payment {
  id: string;
  provider: string;
  status: PaymentStatus;
  amountCents: number;
  amount: string;
  currency: string;
  transactionId: string;
  cardLast4?: string | null;
  failureReason?: string | null;
  createdAt: string;
}

export interface Order {
  id: string;
  reference: string;
  status: OrderStatus;
  buyer: { name: string; email: string; phone?: string | null };
  currency: string;
  totalCents: number;
  total: string;
  expiresAt?: string | null;
  paidAt?: string | null;
  createdAt: string;
  updatedAt: string;
  items: OrderItem[];
  tickets: Ticket[];
  payments: Payment[];
}

export interface TicketLookup {
  id: string;
  code: string;
  status: TicketStatus;
  holderName?: string | null;
  usedAt?: string | null;
  event: {
    id: string;
    title: string;
    slug: string;
    type: EventType;
    status: string;
    startAt: string;
    endAt?: string | null;
    imageUrl?: string | null;
    venue: Venue;
  };
  ticketType: {
    id: string;
    name: string;
    priceCents: number;
    price: string;
    currency: string;
  };
  orderReference: string;
  createdAt: string;
}

export interface Pagination {
  page: number;
  limit: number;
  total: number;
  totalPages: number;
  hasNext: boolean;
  hasPrev: boolean;
}

export interface ListResponse<T> {
  data: T[];
  pagination: Pagination;
}

export interface DataResponse<T> {
  data: T;
}

export interface User {
  id: string;
  email: string;
  name: string;
  phone?: string | null;
  role: Role;
  isActive: boolean;
  createdAt: string;
}

/**
 * Respuesta de /auth/login, /auth/register y /auth/refresh.
 * El access token es un JWT de vida corta; el refresh token es opaco y
 * rotatorio. Ambos viajan en el cuerpo JSON: nunca en cookies.
 */
export interface AuthSession {
  user: User;
  /** JWT de acceso: se guarda solo en memoria. */
  accessToken: string;
  tokenType: 'Bearer';
  /** Segundos de vida del access token. */
  expiresIn: number;
  /** Segundos que le quedan a la sesion (el refresh va en cookie HttpOnly). */
  refreshExpiresIn: number;
}

export interface AdminStats {
  users: number;
  events: number;
  publishedEvents: number;
  orders: number;
  paidOrders: number;
  pendingOrders: number;
  revenueCents: number;
  tickets: number;
  ticketsUsed: number;
}
