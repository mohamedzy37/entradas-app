import { useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import type { Order } from '../api/types';
import { CardFields, EMPTY_CARD, validateCard, type CardValues } from '../components/CardFields';
import { AlertIcon, CheckIcon, ClockIcon, TicketIcon } from '../components/Icons';
import { ErrorState, Loading } from '../components/StateViews';
import { useAsync } from '../hooks/useAsync';
import { ORDER_STATUS_META, TICKET_STATUS_META } from '../lib/constants';
import { formatDateTime } from '../lib/format';

function StatusBadge({ meta }: { meta: { label: string; className: string } }) {
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-bold ${meta.className}`}>{meta.label}</span>
  );
}

function TicketPass({ ticket }: { ticket: Order['tickets'][number] }) {
  const status = TICKET_STATUS_META[ticket.status] ?? TICKET_STATUS_META.VALID;
  return (
    <div className="relative flex items-stretch overflow-hidden rounded-lg border border-line bg-white">
      <div className="flex-1 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">{ticket.ticketTypeName}</p>
        <p className="mt-0.5 font-bold text-ink">{ticket.eventTitle}</p>
        <p className="text-xs text-muted">{formatDateTime(ticket.eventStartAt)}</p>
        <p className="mt-3 font-mono text-lg font-bold tracking-wider text-sky">{ticket.code}</p>
        {ticket.holderName ? <p className="text-xs text-muted">Titular: {ticket.holderName}</p> : null}
      </div>
      <div className="flex flex-col items-center justify-center gap-2 border-l border-dashed border-line bg-gray-50 px-4">
        <TicketIcon className="text-brand" />
        <StatusBadge meta={status} />
      </div>
    </div>
  );
}

export function OrderPage() {
  const { reference = '' } = useParams();
  const order = useAsync(() => api.getOrder(reference), [reference]);

  const [card, setCard] = useState<CardValues>(EMPTY_CARD);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const data = order.data?.data;
  const isPending = data?.status === 'PENDING';

  async function pay(formEvent: FormEvent) {
    formEvent.preventDefault();
    setError(null);
    const cardError = validateCard(card);
    if (cardError) {
      setError(cardError);
      return;
    }
    setSubmitting(true);
    try {
      await api.payOrder(reference, {
        cardNumber: card.cardNumber.replace(/\s+/g, ''),
        cardHolder: card.cardHolder.trim(),
        expiryMonth: Number(card.expiryMonth),
        expiryYear: Number(card.expiryYear),
        cvv: card.cvv.trim(),
      });
      order.reload();
    } catch (paymentError) {
      if (paymentError instanceof ApiError) setError(paymentError.message);
      else setError('No se pudo procesar el pago.');
      order.reload();
    } finally {
      setSubmitting(false);
    }
  }

  if (order.loading) return <Loading label="Cargando tu pedido..." />;
  if (order.error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <ErrorState error={order.error} onRetry={order.reload} />
      </div>
    );
  }
  if (!data) return null;

  const statusMeta = ORDER_STATUS_META[data.status] ?? ORDER_STATUS_META.PENDING;
  const lastRejected = data.payments.find((payment) => payment.status === 'REJECTED');

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <nav className="mb-4 text-sm text-muted">
        <Link to="/eventos" className="text-sky hover:underline">
          Eventos
        </Link>{' '}
        <span>›</span> <span>Pedido {data.reference}</span>
      </nav>

      <div className="rounded-xl border border-line bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm text-muted">Referencia del pedido</p>
            <h1 className="font-mono text-2xl font-extrabold text-ink">{data.reference}</h1>
            <p className="mt-1 text-sm text-muted">Creado el {formatDateTime(data.createdAt)}</p>
          </div>
          <StatusBadge meta={statusMeta} />
        </div>

        {data.status === 'PAID' ? (
          <div className="mt-4 flex items-center gap-2 rounded-lg bg-green-50 px-4 py-3 text-sm font-semibold text-green-800">
            <CheckIcon width={18} height={18} /> ¡Pago completado! Aquí tienes tus entradas.
          </div>
        ) : null}

        {isPending ? (
          <div className="mt-4 flex items-start gap-2 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <ClockIcon width={18} height={18} className="mt-0.5 shrink-0" />
            <span>
              Tu reserva está pendiente de pago.
              {data.expiresAt ? ` Se liberará el ${formatDateTime(data.expiresAt)} si no completas el pago.` : ''}
            </span>
          </div>
        ) : null}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <section className="rounded-xl border border-line bg-white p-5">
            <h2 className="font-bold text-ink">Artículos</h2>
            <ul className="mt-3 space-y-3">
              {data.items.map((item) => (
                <li key={item.id} className="flex items-start justify-between gap-3 border-b border-line pb-3 last:border-0 last:pb-0">
                  <div>
                    <p className="font-semibold text-ink">{item.eventTitle}</p>
                    <p className="text-sm text-muted">
                      {item.quantity} × {item.ticketTypeName} · {formatDateTime(item.eventStartAt)}
                    </p>
                  </div>
                  <span className="font-semibold text-ink">{item.subtotal}</span>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex items-center justify-between border-t border-line pt-4">
              <span className="font-bold text-ink">Total</span>
              <span className="text-xl font-extrabold text-ink">{data.total}</span>
            </div>
          </section>

          {data.tickets.length > 0 ? (
            <section>
              <h2 className="mb-3 font-bold text-ink">Tus entradas ({data.tickets.length})</h2>
              <div className="space-y-3">
                {data.tickets.map((ticket) => (
                  <TicketPass key={ticket.id} ticket={ticket} />
                ))}
              </div>
            </section>
          ) : null}

          {data.payments.length > 0 ? (
            <section className="rounded-xl border border-line bg-white p-5">
              <h2 className="font-bold text-ink">Historial de pagos</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {data.payments.map((payment) => (
                  <li key={payment.id} className="flex items-center justify-between gap-3">
                    <span className="text-muted">
                      {formatDateTime(payment.createdAt)} · {payment.provider}
                      {payment.cardLast4 ? ` · ****${payment.cardLast4}` : ''}
                    </span>
                    <span
                      className={`font-semibold ${
                        payment.status === 'APPROVED' ? 'text-green-700' : 'text-red-600'
                      }`}
                    >
                      {payment.status === 'APPROVED' ? 'Aprobado' : 'Rechazado'} · {payment.amount}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>

        <aside className="lg:sticky lg:top-4 lg:self-start">
          <div className="rounded-xl border border-line bg-white p-5 shadow-sm">
            <h2 className="font-bold text-ink">Comprador</h2>
            <p className="mt-2 text-sm text-ink">{data.buyer.name}</p>
            <p className="text-sm text-muted">{data.buyer.email}</p>
            {data.buyer.phone ? <p className="text-sm text-muted">{data.buyer.phone}</p> : null}

            {isPending ? (
              <form onSubmit={pay} className="mt-5 border-t border-line pt-5">
                <h3 className="font-bold text-ink">Pagar ahora</h3>
                {lastRejected ? (
                  <p className="mt-2 flex items-start gap-2 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
                    <AlertIcon width={14} height={14} className="mt-0.5 shrink-0" />
                    Último intento rechazado: {lastRejected.failureReason ?? 'tarjeta rechazada'}
                  </p>
                ) : null}
                <div className="mt-4">
                  <CardFields value={card} onChange={setCard} />
                </div>
                {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
                <button
                  type="submit"
                  disabled={submitting}
                  className="mt-4 w-full rounded-md bg-sky px-4 py-3 font-bold text-white transition hover:bg-sky-dark disabled:bg-gray-300"
                >
                  {submitting ? 'Procesando...' : `Pagar ${data.total}`}
                </button>
              </form>
            ) : (
              <Link
                to="/eventos"
                className="mt-5 block w-full rounded-md border border-sky px-4 py-3 text-center font-bold text-sky hover:bg-sky/5"
              >
                Seguir explorando eventos
              </Link>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
