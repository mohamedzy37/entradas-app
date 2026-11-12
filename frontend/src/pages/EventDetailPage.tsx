import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { CalendarIcon, ChevronLeftIcon, ClockIcon, MapPinIcon, TicketIcon } from '../components/Icons';
import { ErrorState, Loading } from '../components/StateViews';
import { useAsync } from '../hooks/useAsync';
import { eventTypeEmoji, eventTypeLabel } from '../lib/constants';
import { formatLongDate, formatTime, timeUntil } from '../lib/format';

export function EventDetailPage() {
  const { slug = '' } = useParams();
  const navigate = useNavigate();
  const event = useAsync(() => api.getEvent(slug), [slug]);
  const [quantity, setQuantity] = useState<Record<string, number>>({});

  const detail = event.data?.data;

  const selection = useMemo(() => {
    if (!detail) return [] as Array<{ id: string; name: string; price: string; priceCents: number; qty: number }>;
    return detail.ticketTypes
      .map((ticketType) => ({
        id: ticketType.id,
        name: ticketType.name,
        price: ticketType.price,
        priceCents: ticketType.priceCents,
        qty: quantity[ticketType.id] ?? 0,
      }))
      .filter((item) => item.qty > 0);
  }, [detail, quantity]);

  const totalCents = selection.reduce((sum, item) => sum + item.priceCents * item.qty, 0);
  const totalUnits = selection.reduce((sum, item) => sum + item.qty, 0);
  const totalLabel = new Intl.NumberFormat('es-ES', {
    style: 'currency',
    currency: detail?.currency ?? 'EUR',
  }).format(totalCents / 100);

  function setQty(ticketTypeId: string, next: number, maxPerOrder: number, available: number) {
    const max = Math.min(maxPerOrder, available);
    const clamped = Math.max(0, Math.min(next, max));
    setQuantity((prev) => ({ ...prev, [ticketTypeId]: clamped }));
  }

  function reserve() {
    if (!detail || totalUnits === 0) return;
    const itemsParam = selection.map((item) => `${item.id}:${item.qty}`).join(',');
    navigate(`/checkout?event=${detail.slug}&items=${encodeURIComponent(itemsParam)}`);
  }

  if (event.loading) return <Loading label="Cargando evento..." />;
  if (event.error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <ErrorState error={event.error} onRetry={event.reload} />
      </div>
    );
  }
  if (!detail) return null;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <nav className="mb-4 flex items-center gap-2 text-sm text-muted">
        <Link to="/eventos" className="flex items-center gap-1 text-sky hover:underline">
          <ChevronLeftIcon width={16} height={16} /> Volver a eventos
        </Link>
      </nav>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <div className="overflow-hidden rounded-xl border border-line bg-brand">
            <div className="relative flex h-64 items-center justify-center sm:h-80">
              <span className="absolute text-6xl opacity-40">{eventTypeEmoji(detail.type)}</span>
              {detail.imageUrl ? (
                <img
                  src={detail.imageUrl}
                  alt={detail.title}
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                  }}
                  className="relative h-full w-full object-cover"
                />
              ) : null}
            </div>
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-brand/10 px-3 py-1 text-xs font-bold text-brand">
                {eventTypeEmoji(detail.type)} {eventTypeLabel(detail.type)}
              </span>
              {detail.category ? (
                <span className="rounded-full bg-sky/10 px-3 py-1 text-xs font-bold text-sky">
                  {detail.category.name}
                </span>
              ) : null}
              {detail.isSoldOut ? (
                <span className="rounded-full bg-red-100 px-3 py-1 text-xs font-bold text-red-700">Agotado</span>
              ) : (
                <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-bold text-green-700">
                  Entradas disponibles
                </span>
              )}
            </div>

            <h1 className="mt-3 text-2xl font-extrabold leading-tight text-ink sm:text-3xl">
              {detail.title}
            </h1>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <InfoRow icon={<CalendarIcon width={18} height={18} />} label="Fecha">
                {formatLongDate(detail.startAt)}
              </InfoRow>
              <InfoRow icon={<ClockIcon width={18} height={18} />} label="Hora">
                {formatTime(detail.startAt)} · {timeUntil(detail.startAt)}
              </InfoRow>
              <InfoRow icon={<MapPinIcon width={18} height={18} />} label="Lugar">
                {detail.venue.name}
                <span className="block text-muted">
                  {detail.venue.address}, {detail.venue.city} ({detail.venue.country})
                </span>
              </InfoRow>
              {detail.doorsOpenAt ? (
                <InfoRow icon={<TicketIcon width={18} height={18} />} label="Apertura de puertas">
                  {formatTime(detail.doorsOpenAt)}
                </InfoRow>
              ) : null}
            </div>
          </div>

          {detail.description ? (
            <section className="rounded-xl border border-line bg-white p-5">
              <h2 className="font-bold text-ink">Sobre este evento</h2>
              <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-muted">{detail.description}</p>
            </section>
          ) : null}
        </div>

        <aside className="lg:sticky lg:top-4 lg:self-start">
          <div className="rounded-xl border border-line bg-white p-5 shadow-sm">
            <h2 className="text-lg font-extrabold text-ink">Elige tus entradas</h2>

            <div className="mt-4 space-y-3">
              {detail.ticketTypes.map((ticketType) => {
                const qty = quantity[ticketType.id] ?? 0;
                const max = Math.min(ticketType.maxPerOrder, ticketType.available);
                return (
                  <div key={ticketType.id} className="rounded-lg border border-line p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-bold text-ink">{ticketType.name}</p>
                        {ticketType.description ? (
                          <p className="text-xs text-muted">{ticketType.description}</p>
                        ) : null}
                        <p className="mt-1 text-xs text-muted">
                          {ticketType.soldOut
                            ? 'Agotado'
                            : `${ticketType.available} disponibles · máx. ${ticketType.maxPerOrder}`}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-extrabold text-ink">{ticketType.price}</p>
                      </div>
                    </div>

                    <div className="mt-3 flex items-center justify-between">
                      <span className="text-xs text-muted">Cantidad</span>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          disabled={qty === 0 || ticketType.soldOut}
                          onClick={() => setQty(ticketType.id, qty - 1, ticketType.maxPerOrder, ticketType.available)}
                          className="h-8 w-8 rounded-md border border-line text-lg font-bold text-ink hover:border-sky disabled:opacity-40"
                          aria-label="Quitar una entrada"
                        >
                          −
                        </button>
                        <span className="w-6 text-center font-bold">{qty}</span>
                        <button
                          type="button"
                          disabled={ticketType.soldOut || qty >= max}
                          onClick={() => setQty(ticketType.id, qty + 1, ticketType.maxPerOrder, ticketType.available)}
                          className="h-8 w-8 rounded-md border border-line text-lg font-bold text-ink hover:border-sky disabled:opacity-40"
                          aria-label="Añadir una entrada"
                        >
                          +
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-5 border-t border-line pt-4">
              <div className="flex items-center justify-between text-sm text-muted">
                <span>Entradas seleccionadas</span>
                <span>{totalUnits}</span>
              </div>
              <div className="mt-1 flex items-center justify-between">
                <span className="font-bold text-ink">Total</span>
                <span className="text-xl font-extrabold text-ink">{totalLabel}</span>
              </div>

              <button
                type="button"
                disabled={totalUnits === 0}
                onClick={reserve}
                className="mt-4 w-full rounded-md bg-sky px-4 py-3 font-bold text-white transition hover:bg-sky-dark disabled:cursor-not-allowed disabled:bg-gray-300"
              >
                Reservar entradas
              </button>
              <p className="mt-2 text-center text-xs text-muted">
                Guardamos tus entradas 15 minutos mientras pagas.
              </p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function InfoRow({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-line bg-white p-3">
      <span className="mt-0.5 text-sky">{icon}</span>
      <div className="text-sm">
        <p className="font-semibold text-ink">{label}</p>
        <div className="text-ink">{children}</div>
      </div>
    </div>
  );
}
