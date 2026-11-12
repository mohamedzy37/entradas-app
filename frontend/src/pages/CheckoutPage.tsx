import { useMemo, useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { CardFields, EMPTY_CARD, validateCard, type CardValues } from '../components/CardFields';
import { AlertIcon, ChevronLeftIcon, UserIcon } from '../components/Icons';
import { ErrorState, Loading } from '../components/StateViews';
import { useAsync } from '../hooks/useAsync';
import { formatDateTime } from '../lib/format';

interface BuyerValues {
  name: string;
  email: string;
  phone: string;
}

export function CheckoutPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const eventSlug = params.get('event') ?? '';
  const itemsParam = params.get('items') ?? '';

  const requested = useMemo(() => {
    return itemsParam
      .split(',')
      .map((pair) => {
        const [id, qty] = pair.split(':');
        return { id, qty: Number(qty) };
      })
      .filter((item) => item.id && Number.isFinite(item.qty) && item.qty > 0);
  }, [itemsParam]);

  const event = useAsync(() => api.getEvent(eventSlug), [eventSlug]);

  const [buyer, setBuyer] = useState<BuyerValues>({
    // Precargamos los datos de la cuenta; el usuario puede ajustarlos.
    name: user?.name ?? '',
    email: user?.email ?? '',
    phone: user?.phone ?? '',
  });
  const [card, setCard] = useState<CardValues>(EMPTY_CARD);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const detail = event.data?.data;

  const lines = useMemo(() => {
    if (!detail) return [];
    return requested
      .map(({ id, qty }) => {
        const ticketType = detail.ticketTypes.find((t) => t.id === id);
        if (!ticketType) return null;
        return { ticketType, qty: Math.min(qty, ticketType.maxPerOrder, ticketType.available || qty) };
      })
      .filter((line): line is { ticketType: (typeof detail.ticketTypes)[number]; qty: number } => line !== null);
  }, [detail, requested]);

  const totalCents = lines.reduce((sum, line) => sum + line.ticketType.priceCents * line.qty, 0);
  const currency = detail?.currency ?? 'EUR';
  const totalLabel = new Intl.NumberFormat('es-ES', { style: 'currency', currency }).format(totalCents / 100);

  async function handleSubmit(formEvent: FormEvent) {
    formEvent.preventDefault();
    setFormError(null);

    if (!detail) return;
    if (lines.length === 0) {
      setFormError('No has seleccionado ninguna entrada. Vuelve al evento para elegir tus entradas.');
      return;
    }
    if (buyer.name.trim().length < 3) {
      setFormError('Introduce el nombre completo del comprador.');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(buyer.email.trim())) {
      setFormError('Introduce un correo electrónico válido.');
      return;
    }
    const cardError = validateCard(card);
    if (cardError) {
      setFormError(cardError);
      return;
    }

    setSubmitting(true);
    try {
      const orderResponse = await api.createOrder({
        buyer: {
          name: buyer.name.trim(),
          email: buyer.email.trim(),
          phone: buyer.phone.trim() || undefined,
        },
        items: lines.map((line) => ({ ticketTypeId: line.ticketType.id, quantity: line.qty })),
      });

      const reference = orderResponse.data.reference;

      try {
        await api.payOrder(reference, {
          cardNumber: card.cardNumber.replace(/\s+/g, ''),
          cardHolder: card.cardHolder.trim(),
          expiryMonth: Number(card.expiryMonth),
          expiryYear: Number(card.expiryYear),
          cvv: card.cvv.trim(),
        });
      } catch (paymentError) {
        // El pago fue rechazado: el pedido queda pendiente y se puede reintentar.
        if (paymentError instanceof ApiError && paymentError.status === 402) {
          navigate(`/pedido/${reference}`, { replace: true });
          return;
        }
        throw paymentError;
      }

      navigate(`/pedido/${reference}`, { replace: true });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        // La sesion ha caducado a mitad de la compra: volvemos a pedir acceso.
        navigate('/acceder');
        return;
      }
      setFormError(error instanceof Error ? error.message : 'No se pudo completar la compra.');
    } finally {
      setSubmitting(false);
    }
  }

  if (!eventSlug) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center">
        <AlertIcon className="mx-auto text-amber-500" />
        <h1 className="mt-3 text-xl font-extrabold text-ink">No hay ninguna reserva en curso</h1>
        <p className="mt-2 text-sm text-muted">Elige un evento y selecciona tus entradas para continuar.</p>
        <Link to="/eventos" className="mt-5 inline-block rounded-md bg-sky px-5 py-3 font-bold text-white">
          Explorar eventos
        </Link>
      </div>
    );
  }

  if (event.loading) return <Loading label="Preparando tu reserva..." />;
  if (event.error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <ErrorState error={event.error} onRetry={event.reload} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <nav className="mb-4 flex items-center gap-2 text-sm text-muted">
        <Link to={`/eventos/${eventSlug}`} className="flex items-center gap-1 text-sky hover:underline">
          <ChevronLeftIcon width={16} height={16} /> Volver al evento
        </Link>
      </nav>

      <h1 className="text-2xl font-extrabold text-ink">Finaliza tu compra</h1>
      <p className="text-sm text-muted">Completa tus datos y paga de forma segura (simulada).</p>

      <form onSubmit={handleSubmit} className="mt-6 grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <section className="rounded-xl border border-line bg-white p-5">
            <h2 className="flex items-center gap-2 font-bold text-ink">
              <UserIcon width={18} height={18} className="text-sky" /> Datos del comprador
            </h2>
            <div className="mt-4 space-y-4">
              <label className="block">
                <span className="mb-1 block text-sm font-semibold text-ink">Nombre completo</span>
                <input
                  value={buyer.name}
                  onChange={(e) => setBuyer({ ...buyer, name: e.target.value })}
                  placeholder="Ana García"
                  className="w-full rounded-md border border-line px-3 py-3 text-sm outline-none focus:border-sky focus:ring-2 focus:ring-sky/30"
                />
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1 block text-sm font-semibold text-ink">Correo electrónico</span>
                  <input
                    type="email"
                    value={buyer.email}
                    onChange={(e) => setBuyer({ ...buyer, email: e.target.value })}
                    placeholder="ana@ejemplo.com"
                    className="w-full rounded-md border border-line px-3 py-3 text-sm outline-none focus:border-sky focus:ring-2 focus:ring-sky/30"
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-sm font-semibold text-ink">Teléfono (opcional)</span>
                  <input
                    value={buyer.phone}
                    onChange={(e) => setBuyer({ ...buyer, phone: e.target.value })}
                    placeholder="+34 600 000 000"
                    className="w-full rounded-md border border-line px-3 py-3 text-sm outline-none focus:border-sky focus:ring-2 focus:ring-sky/30"
                  />
                </label>
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-line bg-white p-5">
            <h2 className="font-bold text-ink">Método de pago</h2>
            <div className="mt-4">
              <CardFields value={card} onChange={setCard} />
            </div>
          </section>
        </div>

        <aside className="lg:sticky lg:top-4 lg:self-start">
          <div className="rounded-xl border border-line bg-white p-5 shadow-sm">
            <h2 className="font-extrabold text-ink">Resumen del pedido</h2>

            {detail ? (
              <>
                <div className="mt-3 rounded-lg bg-gray-50 p-3">
                  <p className="font-semibold text-ink">{detail.title}</p>
                  <p className="text-xs text-muted">
                    {detail.venue.name} · {detail.venue.city}
                  </p>
                  <p className="text-xs text-muted">{formatDateTime(detail.startAt)}</p>
                </div>

                <ul className="mt-4 space-y-2">
                  {lines.map((line) => (
                    <li key={line.ticketType.id} className="flex items-start justify-between gap-3 text-sm">
                      <span className="text-ink">
                        {line.qty} × {line.ticketType.name}
                      </span>
                      <span className="font-semibold text-ink">
                        {new Intl.NumberFormat('es-ES', { style: 'currency', currency }).format(
                          (line.ticketType.priceCents * line.qty) / 100,
                        )}
                      </span>
                    </li>
                  ))}
                </ul>

                <div className="mt-4 flex items-center justify-between border-t border-line pt-4">
                  <span className="font-bold text-ink">Total</span>
                  <span className="text-xl font-extrabold text-ink">{totalLabel}</span>
                </div>
              </>
            ) : null}

            {formError ? (
              <div className="mt-4 flex items-start gap-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                <AlertIcon width={16} height={16} className="mt-0.5 shrink-0" />
                <span>{formError}</span>
              </div>
            ) : null}

            <button
              type="submit"
              disabled={submitting || lines.length === 0}
              className="mt-4 w-full rounded-md bg-sky px-4 py-3 font-bold text-white transition hover:bg-sky-dark disabled:cursor-not-allowed disabled:bg-gray-300"
            >
              {submitting ? 'Procesando pago...' : `Pagar ${totalLabel}`}
            </button>
            <p className="mt-2 text-center text-xs text-muted">
              Al confirmar aceptas los términos. Pago simulado, sin cargos reales.
            </p>
          </div>
        </aside>
      </form>
    </div>
  );
}
