import { Link } from 'react-router-dom';
import type { EventSummary } from '../api/types';
import { eventTypeEmoji, eventTypeLabel } from '../lib/constants';
import { formatDateTime, timeUntil } from '../lib/format';
import { MapPinIcon } from './Icons';

function EventImage({ event, className }: { event: EventSummary; className: string }) {
  return (
    <div className={`relative overflow-hidden bg-brand ${className}`}>
      <div className="absolute inset-0 flex items-center justify-center text-4xl opacity-40">
        {eventTypeEmoji(event.type)}
      </div>
      {event.imageUrl ? (
        <img
          src={event.imageUrl}
          alt={event.title}
          loading="lazy"
          onError={(e) => {
            e.currentTarget.style.display = 'none';
          }}
          className="relative h-full w-full object-cover transition duration-500 group-hover:scale-105"
        />
      ) : null}
      <span className="absolute left-2 top-2 rounded bg-white/95 px-2 py-0.5 text-xs font-semibold text-brand shadow">
        {eventTypeEmoji(event.type)} {eventTypeLabel(event.type)}
      </span>
      {event.isSoldOut ? (
        <span className="absolute right-2 top-2 rounded bg-red-600/95 px-2 py-0.5 text-xs font-bold text-white shadow">
          Agotado
        </span>
      ) : null}
    </div>
  );
}

function PriceBlock({ event }: { event: EventSummary }) {
  return (
    <div className="text-right">
      <p className="text-xs text-muted">Desde</p>
      <p className="text-lg font-extrabold text-ink">{event.minPrice ?? '—'}</p>
    </div>
  );
}

export function EventCardRow({ event }: { event: EventSummary }) {
  const available = !event.isSoldOut;
  return (
    <article className="group grid gap-4 rounded-lg border border-line bg-white p-3 transition hover:shadow-lg sm:grid-cols-[220px_1fr_auto]">
      <Link to={`/eventos/${event.slug}`} className="block">
        <EventImage event={event} className="h-40 w-full rounded-md sm:h-full" />
      </Link>

      <div className="min-w-0">
        <Link to={`/eventos/${event.slug}`} className="text-lg font-bold leading-tight text-sky hover:underline">
          {event.title}
        </Link>
        {event.category ? (
          <p className="mt-0.5 text-sm font-semibold text-brand">{event.category.name}</p>
        ) : null}
        <p className="mt-2 flex items-center gap-1 text-sm text-muted">
          <MapPinIcon width={15} height={15} />
          {event.venue.name} · {event.venue.city}
        </p>
        <p className="mt-1 text-sm text-muted">{formatDateTime(event.startAt)}</p>
        <p className="mt-2 inline-block rounded-full bg-green-50 px-2 py-0.5 text-xs font-semibold text-green-700">
          {timeUntil(event.startAt)}
        </p>
        {event.description ? (
          <p className="mt-2 line-clamp-2 text-sm text-muted">{event.description}</p>
        ) : null}
      </div>

      <div className="flex flex-row items-end justify-between gap-3 border-t border-line pt-3 sm:flex-col sm:items-end sm:border-t-0 sm:pt-0">
        <PriceBlock event={event} />
        <Link
          to={`/eventos/${event.slug}`}
          className={`rounded-md px-4 py-2 text-sm font-bold text-white transition ${
            available ? 'bg-sky hover:bg-sky-dark' : 'bg-gray-400'
          }`}
        >
          {available ? 'Ver entradas' : 'Ver detalle'}
        </Link>
      </div>
    </article>
  );
}

export function EventCardGrid({ event }: { event: EventSummary }) {
  return (
    <Link
      to={`/eventos/${event.slug}`}
      className="group flex flex-col overflow-hidden rounded-lg border border-line bg-white transition hover:shadow-lg"
    >
      <EventImage event={event} className="aspect-[16/9] w-full" />
      <div className="flex flex-1 flex-col p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
          {event.category?.name ?? eventTypeLabel(event.type)}
        </p>
        <h3 className="mt-1 line-clamp-2 font-bold leading-snug text-ink group-hover:text-sky">
          {event.title}
        </h3>
        <p className="mt-1 text-sm text-muted">{event.venue.city}</p>
        <p className="text-sm text-muted">{formatDateTime(event.startAt)}</p>
        <div className="mt-auto flex items-end justify-between pt-3">
          <div>
            <p className="text-xs text-muted">Desde</p>
            <p className="font-extrabold text-ink">{event.minPrice ?? '—'}</p>
          </div>
          <span className="rounded-md bg-sky/10 px-3 py-1.5 text-sm font-bold text-sky group-hover:bg-sky group-hover:text-white">
            Ver entradas
          </span>
        </div>
      </div>
    </Link>
  );
}
