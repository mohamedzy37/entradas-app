const dateTimeFormatter = new Intl.DateTimeFormat('es-ES', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
});

const dateFormatter = new Intl.DateTimeFormat('es-ES', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
});

const timeFormatter = new Intl.DateTimeFormat('es-ES', {
  hour: '2-digit',
  minute: '2-digit',
});

/** "vie, 14 oct, 20:00" */
export function formatDateTime(iso: string): string {
  return dateTimeFormatter.format(new Date(iso));
}

/** "viernes, 14 de octubre de 2026" */
export function formatLongDate(iso: string): string {
  return capitalize(dateFormatter.format(new Date(iso)));
}

export function formatTime(iso: string): string {
  return timeFormatter.format(new Date(iso));
}

export function formatDateRange(startIso: string, endIso?: string | null): string {
  if (!endIso) return formatLongDate(startIso);
  const start = new Date(startIso);
  const end = new Date(endIso);
  const sameDay = start.toDateString() === end.toDateString();
  if (sameDay) return `${formatLongDate(startIso)}`;
  return `${formatLongDate(startIso)} — ${formatLongDate(endIso)}`;
}

/** Cuenta atrás legible: "en 3 días", "hoy", "mañana" */
export function timeUntil(iso: string): string {
  const target = new Date(iso).getTime() - Date.now();
  const days = Math.round(target / 86_400_000);
  if (days <= 0) return 'hoy';
  if (days === 1) return 'mañana';
  if (days < 30) return `en ${days} días`;
  const months = Math.round(days / 30);
  return months <= 1 ? 'en 1 mes' : `en ${months} meses`;
}

export function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

const moneyFormatter = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'EUR',
});

export function formatCents(cents: number, currency = 'EUR'): string {
  try {
    return new Intl.NumberFormat('es-ES', { style: 'currency', currency }).format(cents / 100);
  } catch {
    return `${(cents / 100).toFixed(2)} ${currency}`;
  }
}

export function formatMoneyFallback(cents: number | null | undefined, currency = 'EUR'): string {
  if (cents === null || cents === undefined) return '—';
  return formatCents(cents, currency);
}

export { moneyFormatter };
