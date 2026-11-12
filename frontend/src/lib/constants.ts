import type { EventType } from '../api/types';

const EVENT_TYPE_META: Record<EventType, { label: string; emoji: string }> = {
  MUSEUM: { label: 'Museo', emoji: '🏛️' },
  FOOTBALL: { label: 'Fútbol', emoji: '⚽' },
  CINEMA: { label: 'Cine', emoji: '🎬' },
  FESTIVAL: { label: 'Festival', emoji: '🎡' },
  CONCERT: { label: 'Concierto', emoji: '🎶' },
  THEATER: { label: 'Teatro y ópera', emoji: '🎭' },
  OTHER: { label: 'Otro', emoji: '🎫' },
};

export const EVENT_TYPES: EventType[] = [
  'MUSEUM',
  'FOOTBALL',
  'CINEMA',
  'FESTIVAL',
  'CONCERT',
  'THEATER',
  'OTHER',
];

export function eventTypeLabel(type: EventType): string {
  return EVENT_TYPE_META[type]?.label ?? 'Evento';
}

export function eventTypeEmoji(type: EventType): string {
  return EVENT_TYPE_META[type]?.emoji ?? '🎫';
}

export const SORT_OPTIONS = [
  { value: 'date_asc', label: 'Fecha (más próximos)' },
  { value: 'date_desc', label: 'Fecha (más lejanos)' },
  { value: 'price_asc', label: 'Precio (menor primero)' },
  { value: 'price_desc', label: 'Precio (mayor primero)' },
] as const;

export const ORDER_STATUS_META: Record<string, { label: string; className: string }> = {
  PENDING: { label: 'Pendiente de pago', className: 'bg-amber-100 text-amber-800' },
  PAID: { label: 'Pagada', className: 'bg-green-100 text-green-800' },
  CANCELLED: { label: 'Cancelada', className: 'bg-gray-200 text-gray-700' },
  REFUNDED: { label: 'Reembolsada', className: 'bg-purple-100 text-purple-800' },
  EXPIRED: { label: 'Expirada', className: 'bg-red-100 text-red-700' },
};

export const TICKET_STATUS_META: Record<string, { label: string; className: string }> = {
  VALID: { label: 'Válida', className: 'bg-green-100 text-green-800' },
  USED: { label: 'Usada', className: 'bg-gray-200 text-gray-700' },
  CANCELLED: { label: 'Cancelada', className: 'bg-red-100 text-red-700' },
};
